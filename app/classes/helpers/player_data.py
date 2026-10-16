"""Read what a Minecraft Java server saves about each player.

The game keeps, inside the world folder (``level-name`` in server.properties):

- ``playerdata/<uuid>.dat``: NBT with inventory, ender chest, health, position
- ``stats/<uuid>.json``: statistics
- ``advancements/<uuid>.json``: advancements

and ``usercache.json`` (uuid to name) in the server folder. Everything here is
read-only. The game saves player files every few minutes and when a player
leaves, so for players who are online the data can be a few minutes old.

Several Minecraft versions are understood: item ``tag`` (up to 1.20.4) and
``components`` (1.20.5 and newer), armor in ``Inventory`` (up to 1.21.4) or
in ``equipment`` (1.21.5 and newer), and the flat statistics of 1.12.
"""

import json
import logging
import os
import re
import struct
import typing as t
import zlib
from pathlib import Path

from app.classes.helpers import server_properties

logger = logging.getLogger(__name__)

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_NBT_BYTES = 32 * 1024 * 1024
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_DEPTH = 128
MAX_TEXT = 200
# Above this many players the list skips reading every stats file
PLAY_TIME_PLAYER_LIMIT = 2000

GAME_MODES = {0: "survival", 1: "creative", 2: "adventure", 3: "spectator"}
OLD_DIMENSIONS = {
    0: "minecraft:overworld",
    -1: "minecraft:the_nether",
    1: "minecraft:the_end",
}
# Inventory slot numbers used for armor and offhand before 1.21.5
OLD_EQUIPMENT_SLOTS = {
    103: "head",
    102: "chest",
    101: "legs",
    100: "feet",
    -106: "offhand",
}
EQUIPMENT_KEYS = ("head", "chest", "legs", "feet", "offhand")
MAX_HEALTH_IDS = (
    "minecraft:max_health",
    "minecraft:generic.max_health",
    "generic.maxHealth",
)
# 1.12 statistics: "stat.<category>.<id>" to the newer category names
OLD_STAT_CATEGORIES = {
    "mineBlock": "minecraft:mined",
    "craftItem": "minecraft:crafted",
    "useItem": "minecraft:used",
    "breakItem": "minecraft:broken",
    "pickup": "minecraft:picked_up",
    "drop": "minecraft:dropped",
    "killEntity": "minecraft:killed",
    "entityKilledBy": "minecraft:killed_by",
}


class NbtError(ValueError):
    pass


# --------------------------------------------------------------------------
# NBT
# --------------------------------------------------------------------------


def _decode_mutf8(raw: bytes) -> str:
    """Java's modified UTF-8: NUL is C0 80, characters above U+FFFF are pairs."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        text = raw.replace(b"\xc0\x80", b"\x00").decode("utf-8", "surrogatepass")
        return text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    except UnicodeError:
        return raw.decode("utf-8", "replace")


class _NbtReader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def take(self, size: int) -> bytes:
        if size < 0 or self.pos + size > len(self.data):
            raise NbtError("NBT data ends too early")
        chunk = self.data[self.pos : self.pos + size]
        self.pos += size
        return chunk

    def number(self, fmt: str):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def array(self, fmt: str, width: int) -> list:
        length = self.number(">i")
        return list(struct.unpack(f">{max(length, 0)}{fmt}", self.take(length * width)))

    def string(self) -> str:
        return _decode_mutf8(self.take(self.number(">H")))

    def payload(self, tag: int, depth: int):
        if depth > MAX_DEPTH:
            raise NbtError("NBT data is nested too deeply")
        if tag == 1:
            return self.number(">b")
        if tag == 2:
            return self.number(">h")
        if tag == 3:
            return self.number(">i")
        if tag == 4:
            return self.number(">q")
        if tag == 5:
            return self.number(">f")
        if tag == 6:
            return self.number(">d")
        if tag == 7:
            return self.array("b", 1)
        if tag == 8:
            return self.string()
        if tag == 9:
            item_tag = self.number(">B")
            length = self.number(">i")
            if length <= 0:
                return []
            if item_tag == 0:
                raise NbtError("NBT list of end tags")
            return [self.payload(item_tag, depth + 1) for _ in range(length)]
        if tag == 10:
            compound = {}
            while True:
                child_tag = self.number(">B")
                if child_tag == 0:
                    return compound
                name = self.string()
                compound[name] = self.payload(child_tag, depth + 1)
        if tag == 11:
            return self.array("i", 4)
        if tag == 12:
            return self.array("q", 8)
        raise NbtError(f"Unknown NBT tag {tag}")


def _decompress(raw: bytes) -> bytes:
    if raw[:2] == b"\x1f\x8b":
        wbits = 31  # gzip, what the game uses for player files
    elif raw[:1] == b"\x78":
        wbits = 15  # zlib
    else:
        return raw
    decompressor = zlib.decompressobj(wbits)
    try:
        data = decompressor.decompress(raw, MAX_NBT_BYTES + 1)
    except zlib.error as ex:
        raise NbtError(f"Could not decompress NBT data: {ex}") from ex
    if len(data) > MAX_NBT_BYTES or decompressor.unconsumed_tail:
        raise NbtError("NBT data is too large")
    return data


def parse_nbt(raw: bytes) -> dict:
    """Parse a (possibly compressed) NBT file whose root is a compound."""
    reader = _NbtReader(_decompress(raw))
    if reader.number(">B") != 10:
        raise NbtError("NBT root is not a compound")
    reader.string()
    return reader.payload(10, 0)


def _read_limited(path: Path, limit: int) -> bytes:
    with open(path, "rb") as file:
        data = file.read(limit + 1)
    if len(data) > limit:
        raise NbtError(f"{path.name} is too large")
    return data


def read_nbt(path: Path) -> dict:
    return parse_nbt(_read_limited(path, MAX_FILE_BYTES))


def _read_json(path: Path) -> t.Any:
    """Parsed JSON, or None if the file is missing or unreadable."""
    try:
        return json.loads(_read_limited(path, MAX_JSON_BYTES).decode("utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as ex:
        logger.warning(f"Could not read {path}: {ex}")
        return None


# --------------------------------------------------------------------------
# Small helpers for loosely typed game data
# --------------------------------------------------------------------------


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _number(value) -> t.Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _text(value, depth: int = 0) -> str:
    """Plain text from a name: a string, JSON text or a text component."""
    if depth > 20:
        return ""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped[:1] in ("{", "[", '"'):
            try:
                return _text(json.loads(stripped), depth + 1)
            except ValueError:
                pass
        return value[:MAX_TEXT]
    if isinstance(value, dict):
        text = value.get("text")
        text = text if isinstance(text, str) else ""
        if not text and isinstance(value.get("translate"), str):
            text = value["translate"]
        text += "".join(_text(part, depth + 1) for part in _list(value.get("extra")))
        return text[:MAX_TEXT]
    if isinstance(value, list):
        return "".join(_text(part, depth + 1) for part in value)[:MAX_TEXT]
    return ""


def _dimension(value) -> t.Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return OLD_DIMENSIONS.get(value, str(value))
    return None


def _block_pos(value) -> t.Optional[t.List[int]]:
    values = _list(value)
    if len(values) == 3 and all(isinstance(v, int) for v in values):
        return list(values)
    return None


def _location(value) -> t.Optional[dict]:
    """A {dimension, pos: [x, y, z]} compound (last death, 1.21.5 respawn)."""
    value = _dict(value)
    pos = _block_pos(value.get("pos"))
    if pos is None:
        return None
    return {"dimension": _dimension(value.get("dimension")), "position": pos}


# --------------------------------------------------------------------------
# Items
# --------------------------------------------------------------------------


def _enchantments(value) -> t.List[list]:
    """1.20.5+: {levels: {id: level}}; 1.21.5+: {id: level}."""
    value = _dict(value)
    levels = value.get("levels") if isinstance(value.get("levels"), dict) else value
    return [
        [key, level]
        for key, level in levels.items()
        if isinstance(key, str)
        and isinstance(level, int)
        and not isinstance(level, bool)
        and key != "show_in_tooltip"
    ]


def _old_enchantments(value) -> t.List[list]:
    """Up to 1.20.4: [{id, lvl}] (1.12 uses number ids)."""
    found = []
    for entry in _list(value):
        entry = _dict(entry)
        enchant_id, level = entry.get("id"), entry.get("lvl")
        if isinstance(enchant_id, int) and not isinstance(enchant_id, bool):
            enchant_id = f"#{enchant_id}"
        if isinstance(enchant_id, str) and isinstance(level, int):
            found.append([enchant_id, level])
    return found


def parse_item(entry, depth: int = 0) -> t.Optional[dict]:
    """A plain description of one item stack, or None for an empty slot."""
    entry = _dict(entry)
    item_id = entry.get("id")
    if not isinstance(item_id, str) or not item_id or item_id == "minecraft:air":
        return None
    count = entry.get("count", entry.get("Count", 1))
    item: t.Dict[str, t.Any] = {
        "id": item_id[:MAX_TEXT],
        "count": int(count) if _number(count) is not None else 1,
    }
    components = _dict(entry.get("components"))
    tag = _dict(entry.get("tag"))

    name = _text(components.get("minecraft:custom_name")) or _text(
        _dict(tag.get("display")).get("Name")
    )
    if name:
        item["name"] = name

    enchantments = (
        _enchantments(components.get("minecraft:enchantments"))
        + _enchantments(components.get("minecraft:stored_enchantments"))
        + _old_enchantments(tag.get("Enchantments"))
        + _old_enchantments(tag.get("StoredEnchantments"))
        + _old_enchantments(tag.get("ench"))
    )
    if enchantments:
        item["enchantments"] = enchantments

    damage = components.get("minecraft:damage", tag.get("Damage"))
    if isinstance(damage, int) and not isinstance(damage, bool) and damage > 0:
        item["damage"] = damage
    max_damage = components.get("minecraft:max_damage")
    if isinstance(max_damage, int) and not isinstance(max_damage, bool):
        item["max_damage"] = max_damage
    if "minecraft:unbreakable" in components or tag.get("Unbreakable"):
        item["unbreakable"] = True

    potion = components.get("minecraft:potion_contents")
    if isinstance(potion, dict):
        potion = potion.get("potion")
    if potion is None:
        potion = tag.get("Potion")
    if isinstance(potion, str):
        item["potion"] = potion

    if depth == 0:
        # (slot, item); bundles have no slots
        found = [
            (_dict(entry).get("slot"), parse_item(_dict(entry).get("item"), depth + 1))
            for entry in _list(components.get("minecraft:container"))
        ]
        found += [
            (None, parse_item(stack, depth + 1))
            for stack in _list(components.get("minecraft:bundle_contents"))
        ]
        found += [
            (_dict(stack).get("Slot"), parse_item(stack, depth + 1))
            for stack in _list(_dict(tag.get("BlockEntityTag")).get("Items"))
            + _list(tag.get("Items"))
        ]
        contents = []
        for slot, stack in found:
            if not stack:
                continue
            if isinstance(slot, int) and not isinstance(slot, bool) and 0 <= slot < 256:
                stack["slot"] = slot
            contents.append(stack)
        if contents:
            item["contents"] = contents
    return item


def _slots(entries, low: int, high: int) -> t.List[dict]:
    slots = []
    for entry in _list(entries):
        slot = _dict(entry).get("Slot")
        if not isinstance(slot, int) or not low <= slot <= high:
            continue
        item = parse_item(entry)
        if item:
            slots.append({"slot": slot, "item": item})
    return slots


# --------------------------------------------------------------------------
# Player files
# --------------------------------------------------------------------------


def world_folder(server_path) -> t.Optional[Path]:
    """The main world folder, or None if level-name points outside the server."""
    base = Path(server_path).resolve()
    name = None
    try:
        name = server_properties.read_value(base / "server.properties", "level-name")
    except OSError:
        pass
    folder = (base / (name.strip() if name and name.strip() else "world")).resolve()
    if folder != base and base not in folder.parents:
        logger.warning(f"level-name of {base} points outside the server folder")
        return None
    return folder


def _usercache_names(server_path) -> t.Dict[str, str]:
    names = {}
    for entry in _list(_read_json(Path(server_path, "usercache.json"))):
        entry = _dict(entry)
        uuid = str(entry.get("uuid", "")).lower()
        if UUID_RE.match(uuid) and isinstance(entry.get("name"), str):
            names[uuid] = entry["name"][:64]
    return names


def _play_time(custom: dict) -> t.Optional[int]:
    """Ticks played; called play_one_minute before 1.17 (still in ticks)."""
    for key in ("minecraft:play_time", "minecraft:play_one_minute"):
        value = custom.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def normalise_stats(raw) -> t.Optional[t.Dict[str, t.Dict[str, float]]]:
    """{category: {id: value}} using the 1.13+ names for every version."""
    raw = _dict(raw)
    if not raw:
        return None
    stats: t.Dict[str, t.Dict[str, float]] = {}
    if isinstance(raw.get("stats"), dict):
        for category, values in raw["stats"].items():
            if isinstance(category, str) and isinstance(values, dict):
                stats[category] = {
                    key: value
                    for key, value in values.items()
                    if isinstance(key, str) and _number(value) is not None
                }
    else:
        for key, value in raw.items():
            if not key.startswith("stat.") or _number(value) is None:
                continue
            parts = key[len("stat.") :].split(".", 1)
            if len(parts) == 2 and parts[0] in OLD_STAT_CATEGORIES:
                stat_id = parts[1].replace(".", ":", 1) if "." in parts[1] else parts[1]
                stats.setdefault(OLD_STAT_CATEGORIES[parts[0]], {})[stat_id] = value
            elif len(parts) == 1:
                snake = re.sub(r"(?<!^)([A-Z])", r"_\1", parts[0]).lower()
                stats.setdefault("minecraft:custom", {})[f"minecraft:{snake}"] = value
    custom = stats.get("minecraft:custom", {})
    play_time = _play_time(custom)
    if play_time is not None:
        custom["minecraft:play_time"] = play_time
    return stats


def _advancements(raw) -> t.Optional[t.List[dict]]:
    raw = _dict(raw)
    if not raw:
        return None
    done = []
    for key, value in raw.items():
        if not isinstance(value, dict) or "recipes/" in key:
            continue
        if value.get("done") is True:
            times = [
                v for v in _dict(value.get("criteria")).values() if isinstance(v, str)
            ]
            done.append({"id": key, "done_at": max(times) if times else None})
    done.sort(key=lambda adv: adv["done_at"] or "", reverse=True)
    return done


# path -> (mtime_ns, size, ticks played) so the list does not re-read files
_play_time_cache: t.Dict[str, t.Tuple[int, int, t.Optional[int]]] = {}


def _cached_play_time(path: Path) -> t.Optional[int]:
    try:
        stat = path.stat()
    except OSError:
        return None
    key = str(path)
    cached = _play_time_cache.get(key)
    if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2]
    stats = normalise_stats(_read_json(path)) or {}
    ticks = _play_time(stats.get("minecraft:custom", {}))
    _play_time_cache[key] = (stat.st_mtime_ns, stat.st_size, ticks)
    return ticks


def list_players(server_path) -> t.List[dict]:
    """Everyone with saved data on this server, most recently played first."""
    world = world_folder(server_path)
    if world is None:
        return []
    saved: t.Dict[str, float] = {}
    try:
        with os.scandir(world / "playerdata") as entries:
            for entry in entries:
                uuid = entry.name[:-4].lower()
                if not entry.name.endswith(".dat") or not UUID_RE.match(uuid):
                    continue
                try:
                    saved[uuid] = entry.stat().st_mtime
                except OSError:
                    continue
    except OSError:
        return []
    names = _usercache_names(server_path)
    read_play_time = len(saved) <= PLAY_TIME_PLAYER_LIMIT
    players = [
        {
            "uuid": uuid,
            "name": names.get(uuid),
            "last_played": int(mtime),
            "play_time": (
                _cached_play_time(world / "stats" / f"{uuid}.json")
                if read_play_time
                else None
            ),
        }
        for uuid, mtime in saved.items()
    ]
    players.sort(key=lambda player: player["last_played"], reverse=True)
    return players


def _max_health(nbt: dict) -> float:
    for attribute in _list(nbt.get("attributes")) + _list(nbt.get("Attributes")):
        attribute = _dict(attribute)
        if attribute.get("id", attribute.get("Name")) in MAX_HEALTH_IDS:
            base = _number(attribute.get("base", attribute.get("Base")))
            if base:
                return base
    return 20.0


def _spawn(nbt: dict) -> t.Optional[dict]:
    """Bed or respawn anchor; None means the world spawn."""
    if "respawn" in nbt:
        return _location(nbt["respawn"])
    coords = [nbt.get(key) for key in ("SpawnX", "SpawnY", "SpawnZ")]
    if all(isinstance(v, int) for v in coords):
        return {
            "dimension": _dimension(nbt.get("SpawnDimension", "minecraft:overworld")),
            "position": coords,
        }
    return None


def player_from_nbt(nbt: dict) -> dict:
    equipment = {}
    for entry in _list(nbt.get("Inventory")):
        slot = _dict(entry).get("Slot")
        if slot in OLD_EQUIPMENT_SLOTS:
            item = parse_item(entry)
            if item:
                equipment[OLD_EQUIPMENT_SLOTS[slot]] = item
    for key, value in _dict(nbt.get("equipment")).items():
        item = parse_item(value)
        if item and key in EQUIPMENT_KEYS:
            equipment[key] = item

    position = [_number(v) for v in _list(nbt.get("Pos"))[:3]]
    selected = nbt.get("SelectedItemSlot")
    return {
        "profile": {
            "health": _number(nbt.get("Health")),
            "max_health": _max_health(nbt),
            "food": _number(nbt.get("foodLevel")),
            "saturation": _number(nbt.get("foodSaturationLevel")),
            "xp_level": _number(nbt.get("XpLevel")),
            "xp_progress": _number(nbt.get("XpP")),
            "game_mode": GAME_MODES.get(nbt.get("playerGameType")),
            "dimension": _dimension(nbt.get("Dimension")),
            "position": (
                [round(v, 1) for v in position]
                if len(position) == 3 and None not in position
                else None
            ),
            "spawn": _spawn(nbt),
            "last_death": _location(nbt.get("LastDeathLocation")),
            "selected_slot": selected if isinstance(selected, int) else None,
            "data_version": _number(nbt.get("DataVersion")),
        },
        "inventory": _slots(nbt.get("Inventory"), 0, 35),
        "equipment": equipment,
        "ender_chest": _slots(nbt.get("EnderItems"), 0, 26),
    }


def has_player(server_path, uuid: str) -> bool:
    """Whether the server has saved anything about this player."""
    uuid = str(uuid).lower()
    if not UUID_RE.match(uuid):
        return False
    world = world_folder(server_path)
    if world is None:
        return False
    return any(
        (world / folder / f"{uuid}{suffix}").is_file()
        for folder, suffix in (
            ("playerdata", ".dat"),
            ("stats", ".json"),
            ("advancements", ".json"),
        )
    )


def player_details(server_path, uuid: str) -> t.Optional[dict]:
    """All saved data about one player, or None if the server has none."""
    uuid = str(uuid).lower()
    if not UUID_RE.match(uuid):
        raise ValueError("Not a player UUID")
    world = world_folder(server_path)
    if world is None:
        return None
    details: t.Dict[str, t.Any] = {
        "uuid": uuid,
        "name": _usercache_names(server_path).get(uuid),
        "saved_at": None,
        "profile": None,
        "inventory": None,
        "equipment": None,
        "ender_chest": None,
        "playerdata_error": False,
        "stats": normalise_stats(_read_json(world / "stats" / f"{uuid}.json")),
        "advancements": _advancements(
            _read_json(world / "advancements" / f"{uuid}.json")
        ),
    }
    dat = world / "playerdata" / f"{uuid}.dat"
    if dat.is_file():
        try:
            details["saved_at"] = int(dat.stat().st_mtime)
            details.update(player_from_nbt(read_nbt(dat)))
        except (OSError, NbtError, struct.error) as ex:
            logger.warning(f"Could not read {dat}: {ex}")
            details["playerdata_error"] = True
    elif details["stats"] is None and details["advancements"] is None:
        return None
    return details
