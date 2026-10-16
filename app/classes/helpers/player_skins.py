"""Player skins for the inventory picture in the player details window.

Only used once a super user has made the item pictures, which is when Crafty
has been allowed to fetch Minecraft's art from Mojang. Players with a Mojang
account (online-mode servers) get their own skin from Mojang's session server,
kept in app/config/player_skins/ for a few hours. Everyone else, and anyone
whose skin cannot be fetched, gets the default skin the game would give them,
taken from the item pictures (see item_icons.py).

Skins are returned in the 64x64 layout with the game's own clean-up applied,
so the page can draw any skin the same way.
"""

import base64
import binascii
import io
import json
import logging
import re
import threading
import time
import typing as t
from pathlib import Path

import requests
from PIL import Image

from app.classes.helpers.item_icons import DEFAULT_SKINS as DEFAULT_NAMES, ItemIcons

logger = logging.getLogger(__name__)

PROFILE_URL = "https://sessionserver.mojang.com/session/minecraft/profile/{}"
TEXTURE_RE = re.compile(
    r"^https?://textures\.minecraft\.net/texture/([0-9a-f]{1,128})$"
)
UUID_RE = re.compile(r"^[0-9a-f]{32}$")
FRESH_SECONDS = 6 * 3600
RETRY_SECONDS = 10 * 60
MAX_BYTES = 256 * 1024
TIMEOUT = 5


def _hex(uuid: str) -> t.Optional[str]:
    value = str(uuid).lower().replace("-", "")
    return value if UUID_RE.match(value) else None


def _java_hash(uuid_hex: str) -> int:
    """java.util.UUID.hashCode() of the UUID."""
    hilo = int(uuid_hex[:16], 16) ^ int(uuid_hex[16:], 16)
    value = ((hilo >> 32) ^ hilo) & 0xFFFFFFFF
    return value - (1 << 32) if value >= 1 << 31 else value


def default_skin(uuid_hex: str) -> t.Tuple[str, str]:
    """(name, model) of the default skin the game gives this UUID."""
    index = _java_hash(uuid_hex) % (2 * len(DEFAULT_NAMES))
    model = "slim" if index < len(DEFAULT_NAMES) else "wide"
    return DEFAULT_NAMES[index % len(DEFAULT_NAMES)], model


def _copy_rect(img: Image.Image, x, y, dx, dy, width, height) -> None:
    """Copy a rectangle by (dx, dy), mirrored left to right."""
    part = img.crop((x, y, x + width, y + height))
    img.paste(part.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (x + dx, y + dy))


def _no_alpha(img: Image.Image, box) -> None:
    region = img.crop(box)
    region.putalpha(255)
    img.paste(region, box[:2])


def normalise(img: Image.Image) -> Image.Image:
    """The game's clean-up of a downloaded skin (SkinTextureDownloader).

    Old 64x32 skins become 64x64 with the left arm and leg mirrored from the
    right ones; the inner layer is made opaque.
    """
    if img.width != 64 or img.height not in (32, 64):
        raise ValueError(f"A skin is 64x64 or 64x32, not {img.width}x{img.height}")
    img = img.convert("RGBA")
    legacy = img.height == 32
    if legacy:
        full = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        full.paste(img, (0, 0))
        img = full
        for rect in (
            (4, 16, 16, 32, 4, 4),
            (8, 16, 16, 32, 4, 4),
            (0, 20, 24, 32, 4, 12),
            (4, 20, 16, 32, 4, 12),
            (8, 20, 8, 32, 4, 12),
            (12, 20, 16, 32, 4, 12),
            (44, 16, -8, 32, 4, 4),
            (48, 16, -8, 32, 4, 4),
            (40, 20, 0, 32, 4, 12),
            (44, 20, -8, 32, 4, 12),
            (48, 20, -16, 32, 4, 12),
            (52, 20, -8, 32, 4, 12),
        ):
            _copy_rect(img, *rect)
    _no_alpha(img, (0, 0, 32, 16))
    if legacy:
        # Old skins often filled the hat with a solid colour: hide it then
        hat = img.crop((32, 0, 64, 32))
        if min(hat.getchannel("A").getdata()) >= 128:
            img.paste((0, 0, 0, 0), (32, 0, 64, 32))
    _no_alpha(img, (0, 16, 64, 32))
    _no_alpha(img, (16, 48, 48, 64))
    return img


def _png(img: Image.Image) -> bytes:
    data = io.BytesIO()
    img.save(data, "PNG")
    return data.getvalue()


class PlayerSkins:
    """Finds and caches skins; safe to call from several threads."""

    _instances: t.Dict[str, "PlayerSkins"] = {}
    _instances_lock = threading.Lock()

    def __init__(self, config_dir):
        self.config_dir = Path(config_dir)
        self.folder = self.config_dir / "player_skins"
        self._failed: t.Dict[str, float] = {}
        self._lock = threading.Lock()

    @classmethod
    def get(cls, config_dir) -> "PlayerSkins":
        key = str(config_dir)
        with cls._instances_lock:
            if key not in cls._instances:
                cls._instances[key] = cls(config_dir)
            return cls._instances[key]

    def skin(self, uuid: str) -> t.Optional[t.Tuple[bytes, str]]:
        """(PNG bytes, "wide" or "slim"), or None without item pictures."""
        uuid_hex = _hex(uuid)
        if uuid_hex is None:
            raise ValueError("Not a player UUID")
        if not ItemIcons.get(self.config_dir).info():
            return None
        # Version 4 UUIDs are Mojang accounts; offline-mode players have
        # version 3 ones made from their name and only a default skin
        if uuid_hex[12] == "4":
            found = self._cached(uuid_hex, fresh_only=True)
            if found is None and self._may_ask(uuid_hex):
                found = self._fetch(uuid_hex)
            if found is None:
                found = self._cached(uuid_hex, fresh_only=False)
            if found is not None:
                return found
        return self._default(uuid_hex)

    def _default(self, uuid_hex: str) -> t.Optional[t.Tuple[bytes, str]]:
        name, model = default_skin(uuid_hex)
        path = ItemIcons.get(self.config_dir).path(f"_skin_{model}_{name}")
        if path is None:
            # Pictures made before default skins were kept
            return None
        try:
            with Image.open(path) as img:
                return _png(normalise(img)), model
        except (OSError, ValueError) as ex:
            # The pictures are being made again, or the game changed its skins
            logger.debug(f"Could not read the default skin {name}: {ex}")
            return None

    def _cached(self, uuid_hex: str, fresh_only: bool):
        try:
            info = json.loads(
                (self.folder / f"{uuid_hex}.json").read_text(encoding="utf-8")
            )
            if fresh_only and time.time() - float(info["checked"]) > FRESH_SECONDS:
                return None
            if info.get("default"):
                return self._default(uuid_hex)
            model = "slim" if info.get("model") == "slim" else "wide"
            return (self.folder / f"{uuid_hex}.png").read_bytes(), model
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _may_ask(self, uuid_hex: str) -> bool:
        """Do not ask Mojang again soon after it failed."""
        with self._lock:
            failed = self._failed.get(uuid_hex)
            if failed and time.time() - failed < RETRY_SECONDS:
                return False
            if len(self._failed) > 1000:
                self._failed.clear()
            return True

    def _fetch(self, uuid_hex: str) -> t.Optional[t.Tuple[bytes, str]]:
        try:
            found = self._download(uuid_hex)
        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
            OSError,
            Image.DecompressionBombError,
        ) as ex:
            logger.info(f"Could not get the skin of {uuid_hex} from Mojang: {ex}")
            with self._lock:
                self._failed[uuid_hex] = time.time()
            return None
        info = {"checked": time.time()}
        if found is None:
            info["default"] = True
        else:
            info["model"] = found[1]
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            if found is not None:
                self._write(f"{uuid_hex}.png", found[0])
            self._write(f"{uuid_hex}.json", json.dumps(info).encode("utf-8"))
        except OSError as ex:
            logger.warning(f"Could not keep the skin of {uuid_hex}: {ex}")
        return found if found is not None else self._default(uuid_hex)

    def _write(self, name: str, data: bytes) -> None:
        """Write a file in one step, so a reader never sees half of it."""
        tmp = self.folder / f"{name}.{threading.get_ident()}.tmp"
        tmp.write_bytes(data)
        tmp.replace(self.folder / name)

    @staticmethod
    def _download(uuid_hex: str) -> t.Optional[t.Tuple[bytes, str]]:
        """The account's own skin, or None if it uses a default skin."""
        response = requests.get(PROFILE_URL.format(uuid_hex), timeout=TIMEOUT)
        if response.status_code in (204, 404):
            # No such account
            return None
        response.raise_for_status()
        textures = None
        for prop in response.json().get("properties", []):
            if isinstance(prop, dict) and prop.get("name") == "textures":
                try:
                    textures = json.loads(base64.b64decode(prop["value"]))
                except (binascii.Error, UnicodeDecodeError) as ex:
                    raise ValueError("Unreadable textures") from ex
        skin = (textures or {}).get("textures", {}).get("SKIN")
        if not isinstance(skin, dict):
            return None
        match = TEXTURE_RE.match(str(skin.get("url", "")))
        if not match:
            raise ValueError("Unexpected skin address")
        metadata = skin.get("metadata")
        slim = isinstance(metadata, dict) and metadata.get("model") == "slim"
        with requests.get(
            f"https://textures.minecraft.net/texture/{match.group(1)}",
            timeout=TIMEOUT,
            stream=True,
        ) as download:
            download.raise_for_status()
            data = b""
            for chunk in download.iter_content(64 * 1024):
                data += chunk
                if len(data) > MAX_BYTES:
                    raise ValueError("Skin is too big")
        with Image.open(io.BytesIO(data)) as img:
            if img.format != "PNG" or img.width != 64 or img.height not in (32, 64):
                raise ValueError("Not a skin picture")
            return _png(normalise(img)), "slim" if slim else "wide"
