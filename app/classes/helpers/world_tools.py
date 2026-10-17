"""World tools: find a server's world and its dimensions, zip it for download,
and reset the Nether or the End.

Java worlds come in three layouts, all handled here:

- vanilla up to 1.21: the overworld in the world folder itself, the Nether in
  ``DIM-1`` and the End in ``DIM1`` inside it
- Bukkit, Spigot and Paper: ``<world>_nether/DIM-1`` and
  ``<world>_the_end/DIM1`` next to the world folder
- vanilla 26.1 and newer: ``dimensions/minecraft/<dimension>`` inside it

Up to 1.21 the ender dragon fight is saved in ``level.dat`` (``DragonFight``),
so resetting the End also removes it there: a new End with the old "dragon
killed" record gets no dragon, exit portal or gateways. From 26.1 it is in the
End's own folder and goes with it.

Bedrock keeps every dimension in one LevelDB database in
``worlds/<level-name>``, so only downloading works there.
"""

import logging
import os
import re
import secrets
import shutil
import struct
import threading
import time
import typing as t
import zipfile
from pathlib import Path

from app.classes.helpers import player_data, server_properties

logger = logging.getLogger(__name__)

OVERWORLD = "overworld"
NETHER = "the_nether"
END = "the_end"
RESETTABLE = (NETHER, END)
# Region files and the like are compressed already: storing them is as small
# and much faster
STORED_SUFFIXES = (".mca", ".mcc", ".dat", ".dat_old", ".gz", ".zip", ".ldb")
SKIPPED_FILES = ("session.lock",)
DRAGON_FIGHT_TAGS = (
    ("Data", "DragonFight"),  # 1.16 to 1.21
    ("Data", "DimensionData", "1", "DragonFight"),  # 1.9 to 1.15
)
DOWNLOAD_LIFETIME = 3600


class WorldError(Exception):
    """A world tool cannot run; ``code`` is the API's error name."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------
# Finding the world
# --------------------------------------------------------------------------


def _inside(base: Path, path: Path) -> bool:
    return base in path.resolve().parents


def java_world(server_path) -> t.Optional[Path]:
    """The main world folder of a Java server, or None if level-name points
    at the server folder itself or outside it."""
    world = player_data.world_folder(server_path)
    if world is None or not _inside(Path(server_path).resolve(), world):
        return None
    return world


def bedrock_world(server_path) -> t.Optional[Path]:
    base = Path(server_path).resolve()
    try:
        name = server_properties.read_value(base / "server.properties", "level-name")
    except OSError:
        name = None
    name = (name or "").strip() or "Bedrock level"
    folder = (base / "worlds" / name).resolve()
    if (base / "worlds") not in folder.parents:
        logger.warning(f"level-name of {base} points outside its worlds folder")
        return None
    return folder


def _real_folder(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink()


def dimension_folders(world: Path) -> t.Dict[str, t.List[Path]]:
    """The folders holding each dimension's chunks that exist, in any layout."""
    nether_world = world.with_name(world.name + "_nether")
    end_world = world.with_name(world.name + "_the_end")
    new = Path("dimensions", "minecraft")
    candidates = {
        OVERWORLD: [world / new / OVERWORLD]
        + [world / name for name in ("region", "entities", "poi")],
        NETHER: [
            world / new / NETHER,
            world / "DIM-1",
            nether_world / "DIM-1",
            nether_world / new / NETHER,
        ],
        END: [
            world / new / END,
            world / "DIM1",
            end_world / "DIM1",
            end_world / new / END,
        ],
    }
    return {
        dimension: [path for path in paths if _real_folder(path)]
        for dimension, paths in candidates.items()
    }


def world_roots(server_path, server_type: str) -> t.List[Path]:
    """The folders that make up the world, as they go into the zip."""
    if server_type == "minecraft-bedrock":
        world = bedrock_world(server_path)
        return [world] if world and _real_folder(world) else []
    if server_type != "minecraft-java":
        return []
    world = java_world(server_path)
    if world is None or not _real_folder(world):
        return []
    roots = [world]
    for suffix in ("_nether", "_the_end"):
        sibling = world.with_name(world.name + suffix)
        if _real_folder(sibling):
            roots.append(sibling)
    return roots


def folder_size(path: Path) -> int:
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for name in filenames:
            try:
                total += os.lstat(os.path.join(dirpath, name)).st_size
            except OSError:
                continue
    return total


# --------------------------------------------------------------------------
# What the page shows
# --------------------------------------------------------------------------


def _read_nbt_or_none(path: Path) -> t.Optional[dict]:
    if not path.is_file():
        return None
    try:
        return player_data.read_nbt(path)
    except (OSError, player_data.NbtError, struct.error) as ex:
        logger.warning(f"Could not read {path}: {ex}")
        return None


def _number(value) -> t.Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def level_info(world: Path) -> dict:
    """Version, seed and last save of a Java world, as far as they are known."""
    data = (_read_nbt_or_none(world / "level.dat") or {}).get("Data")
    data = data if isinstance(data, dict) else {}
    version = data.get("Version")
    version = version.get("Name") if isinstance(version, dict) else None
    settings = data.get("WorldGenSettings")
    seed = _number(settings.get("seed")) if isinstance(settings, dict) else None
    if seed is None:
        seed = _number(data.get("RandomSeed"))
    if seed is None:
        # 26.1 and newer keep it in a file of its own
        saved = _read_nbt_or_none(
            world / "data" / "minecraft" / "world_gen_settings.dat"
        )
        saved = saved or {}
        inner = saved.get("data")
        seed = _number((inner if isinstance(inner, dict) else saved).get("seed"))
    last_played = _number(data.get("LastPlayed"))
    return {
        "version": version if isinstance(version, str) else None,
        "seed": str(seed) if seed is not None else None,
        "last_played": last_played // 1000 if last_played else None,
    }


def overview(server_path, server_type: str) -> t.Optional[dict]:
    """Everything the World page shows, or None for games it does not know."""
    base = Path(server_path).resolve()
    if server_type == "minecraft-bedrock":
        world = bedrock_world(base)
    elif server_type == "minecraft-java":
        world = java_world(base)
    else:
        return None
    roots = world_roots(base, server_type)
    info: t.Dict[str, t.Any] = {
        "edition": "bedrock" if server_type == "minecraft-bedrock" else "java",
        "name": world.name if world else None,
        "folder": world.relative_to(base).as_posix() if world else None,
        "exists": bool(roots),
        "folders": [root.relative_to(base).as_posix() for root in roots],
        "size": sum(folder_size(root) for root in roots),
        "version": None,
        "seed": None,
        "last_played": None,
        "dimensions": None,
    }
    if info["edition"] == "java" and roots:
        info.update(level_info(roots[0]))
        players = player_data.players_by_dimension(base)
        info["dimensions"] = [
            {
                "id": dimension,
                "size": sum(folder_size(folder) for folder in folders),
                "exists": bool(folders),
                "folders": [folder.relative_to(base).as_posix() for folder in folders],
                "players": players.get(f"minecraft:{dimension}", []),
                "resettable": dimension in RESETTABLE,
            }
            for dimension, folders in dimension_folders(roots[0]).items()
        ]
    return info


# --------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------


def zip_world(server_path, roots: t.List[Path], target: Path) -> int:
    """Zip the world folders with paths relative to the server folder, so the
    zip unpacks straight into a server. Returns the number of files."""
    base = Path(server_path).resolve()
    count = 0
    with zipfile.ZipFile(
        target, "w", zipfile.ZIP_DEFLATED, allowZip64=True, compresslevel=6
    ) as archive:
        for root in roots:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = sorted(
                    name
                    for name in dirnames
                    if not os.path.islink(os.path.join(dirpath, name))
                )
                for name in sorted(filenames):
                    path = Path(dirpath, name)
                    if name in SKIPPED_FILES or path.is_symlink():
                        continue
                    stored = name.lower().endswith(STORED_SUFFIXES)
                    try:
                        archive.write(
                            path,
                            path.relative_to(base).as_posix(),
                            zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED,
                        )
                    except FileNotFoundError:
                        # Deleted by the game since the folder was listed
                        continue
                    count += 1
    return count


def download_name(server_name: str, world_name: str) -> str:
    def clean(text: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-.") or "world"

    stamp = time.strftime("%Y-%m-%d-%H%M")
    return f"{clean(server_name)}-{clean(world_name)}-{stamp}.zip"


class WorldDownloads:
    """Zips of a server's world, each made for one user and fetched once with
    its token. A user has at most one per server: a new one replaces it.

    A job is ``zipping``, then ``ready`` (with a token) or ``failed``.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: t.Dict[t.Tuple[str, str], dict] = {}

    def start(self, server_id: str, user_id, folder: Path) -> None:
        """A zip is being made in ``folder`` (deleted with the job)."""
        job = {"state": "zipping", "folder": folder, "time": time.time()}
        with self._lock:
            old = self._jobs.get((server_id, str(user_id)))
            self._jobs[(server_id, str(user_id))] = job
        if old:
            shutil.rmtree(old["folder"], ignore_errors=True)

    def _set(self, server_id: str, user_id, fields: dict) -> t.Optional[Path]:
        """Update a zip being made; returns its folder, or None if there is no
        such zip any more."""
        with self._lock:
            job = self._jobs.get((server_id, str(user_id)))
            if job is None or job["state"] != "zipping":
                return None
            job.update(fields, time=time.time())
            return job["folder"]

    def finish(self, server_id: str, user_id, path: Path, files: int, saved):
        ready = {
            "state": "ready",
            "token": secrets.token_hex(16),
            "path": path,
            "filename": path.name,
            "size": path.stat().st_size,
            "files": files,
            "saved": saved,
        }
        if self._set(server_id, user_id, ready) is None:
            shutil.rmtree(path.parent, ignore_errors=True)

    def fail(self, server_id: str, user_id, error: str, message: str) -> None:
        folder = self._set(
            server_id, user_id, {"state": "failed", "error": error, "message": message}
        )
        if folder is not None:
            shutil.rmtree(folder, ignore_errors=True)

    def status(self, server_id: str, user_id) -> t.Optional[dict]:
        """What the page shows about the user's zip: no paths."""
        with self._lock:
            job = self._jobs.get((server_id, str(user_id)))
            if job is None:
                return None
            return {
                key: value
                for key, value in job.items()
                if key not in ("folder", "path")
            }

    def take(self, token: str, user_id, server_id: str) -> t.Optional[Path]:
        """The zip for this token, which stops working; None if unknown."""
        with self._lock:
            job = self._jobs.get((server_id, str(user_id)))
            if (
                job is None
                or job["state"] != "ready"
                or not secrets.compare_digest(job["token"], token)
            ):
                return None
            del self._jobs[(server_id, str(user_id))]
        return job["path"]

    def purge(self, older_than: float = DOWNLOAD_LIFETIME) -> None:
        """Forget zips nobody fetched in time, and failures, and delete their
        folders."""
        now = time.time()
        with self._lock:
            old = [
                key
                for key, job in self._jobs.items()
                if job["state"] != "zipping" and now - job["time"] > older_than
            ]
            folders = [self._jobs.pop(key)["folder"] for key in old]
        for folder in folders:
            shutil.rmtree(folder, ignore_errors=True)


downloads = WorldDownloads()


# --------------------------------------------------------------------------
# One world tool at a time per server
# --------------------------------------------------------------------------

_busy_lock = threading.Lock()
_busy: t.Dict[str, str] = {}


def begin(server_id: str, task: str) -> t.Optional[str]:
    """Mark the server busy with ``task``; returns the running task instead
    if there already is one."""
    with _busy_lock:
        if server_id in _busy:
            return _busy[server_id]
        _busy[server_id] = task
        return None


def end(server_id: str) -> None:
    with _busy_lock:
        _busy.pop(server_id, None)


def busy(server_id: str) -> t.Optional[str]:
    """The world tool running on the server, if any."""
    with _busy_lock:
        return _busy.get(server_id)


# --------------------------------------------------------------------------
# Reset
# --------------------------------------------------------------------------


def _without_dragon_fight(level_dat: Path) -> t.Optional[bytes]:
    """level.dat without its dragon fight record, or None if it has none."""
    raw = level_dat.read_bytes()
    changed = None
    for path in DRAGON_FIGHT_TAGS:
        smaller = player_data.remove_tag(changed or raw, path)
        if smaller is not None:
            changed = smaller
    return changed


def reset_dimension(server_path, dimension: str) -> dict:
    """Delete the Nether or the End so the game makes a new one. The server
    must be stopped. Returns the removed folders and whether the dragon fight
    record was removed."""
    if dimension not in RESETTABLE:
        raise WorldError("INVALID_DIMENSION", "Only the Nether or the End")
    base = Path(server_path).resolve()
    world = java_world(base)
    if world is None or not _real_folder(world):
        raise WorldError("WORLD_NOT_FOUND", "This server has no world folder")
    folders = dimension_folders(world)[dimension]
    for folder in folders:
        if not _inside(base, folder):
            raise WorldError("WORLD_NOT_FOUND", f"{folder} is outside the server")

    # The dragon record first: if that fails nothing is deleted, and a kept
    # End without it is fine (the game looks at the End again)
    rewrites = {}
    if dimension == END:
        for level_dat in (
            world / "level.dat",
            world.with_name(world.name + "_the_end") / "level.dat",
        ):
            if level_dat.is_file() and not level_dat.is_symlink():
                try:
                    changed = _without_dragon_fight(level_dat)
                except (OSError, player_data.NbtError, struct.error) as ex:
                    raise WorldError(
                        "LEVEL_DAT_ERROR", f"Could not read {level_dat.name}: {ex}"
                    ) from ex
                if changed is not None:
                    rewrites[level_dat] = changed
    if not folders and not rewrites:
        raise WorldError("NOTHING_TO_RESET", "This dimension has not been made yet")

    for level_dat, data in rewrites.items():
        temp = level_dat.with_name(level_dat.name + ".tmp")
        temp.write_bytes(data)
        shutil.copymode(level_dat, temp)
        os.replace(temp, level_dat)
    for folder in folders:
        shutil.rmtree(folder)
    return {
        "removed": [folder.relative_to(base).as_posix() for folder in folders],
        "dragon_reset": bool(rewrites),
    }
