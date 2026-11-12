"""Data packs from Modrinth, in the world's datapacks folder.

Minecraft loads every .zip file and every folder with a pack.mcmeta in
``<world>/datapacks``, on any Java server (vanilla too). A zip turned off
here is renamed ``x.zip.disabled``, which the game skips; a pack folder can
only be removed, because the game loads a folder whatever its name. A
running server picks up the changes with /minecraft:reload or a restart.
"""

import logging
import shutil
from pathlib import Path

from app.classes.helpers import modrinth, world_tools
from app.classes.helpers.modrinth import ModrinthError

logger = logging.getLogger(__name__)

FOLDER = "datapacks"
LOADERS = ["datapack"]
DISABLED = ".zip.disabled"
ACTIONS = ("enable", "disable", "remove")
# A pack and the packs it needs
MAX_INSTALLS = 6


def safe_zip_name(name: str) -> bool:
    return (
        isinstance(name, str)
        and 4 < len(name) <= 200
        and name.lower().endswith(".zip")
        and not name.startswith(".")
        and Path(name).name == name
        and not any(c in name for c in "/\\\0:")
    )


def world_folder(server_path) -> Path:
    world = world_tools.java_world(server_path)
    if world is None:
        raise ModrinthError(
            "BAD_FOLDER", "level-name in server.properties points outside the server"
        )
    return world


def pack_folder(server_path) -> Path:
    """<world>/datapacks, refused when it is a link or leads elsewhere."""
    world = world_folder(server_path)
    folder = world / FOLDER
    if folder.is_symlink() or (
        folder.exists() and folder.resolve().parent != world.resolve()
    ):
        raise ModrinthError("BAD_FOLDER", "The datapacks folder is a link")
    return folder


def local_packs(server_path):
    """The zips (also the turned off ones) and pack folders in the datapacks
    folder, without asking Modrinth."""
    folder = pack_folder(server_path)
    packs = []
    if not folder.is_dir():
        return packs
    for path in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        name = path.name
        lower = name.lower()
        if path.is_symlink() or name.startswith("."):
            continue
        if path.is_dir():
            if not (path / "pack.mcmeta").is_file():
                continue
            size, enabled, is_folder = world_tools.folder_size(path), True, True
        elif path.is_file() and (lower.endswith(".zip") or lower.endswith(DISABLED)):
            size, enabled, is_folder = (
                path.stat().st_size,
                lower.endswith(".zip"),
                False,
            )
        else:
            continue
        packs.append(
            {
                "file": name,
                "folder": is_folder,
                "size": size,
                "enabled": enabled,
                "project_id": None,
                "title": None,
                "slug": None,
                "icon_url": None,
                "version": None,
                "version_id": None,
                "update": None,
            }
        )
    return packs


def installed(server_path, game_version=None):
    """The packs in the datapacks folder, with the Modrinth project of each
    zip (None for packs from elsewhere) and whether there is a newer one."""
    folder = pack_folder(server_path)
    packs = local_packs(server_path)
    for pack in packs:
        if not pack["folder"]:
            pack["sha1"] = modrinth.sha1_of(folder / pack["file"])
    return modrinth.identify(packs, LOADERS, game_version)


def change_pack(server_path, name: str, action: str):
    """Turn a zip off (x.zip.disabled), on again, or remove a zip or a pack
    folder. Returns the new name, or None when it was removed."""
    if action not in ACTIONS:
        raise ModrinthError("INVALID_ACTION", "action: enable, disable or remove")
    # Only names that are in the folder: nothing else can be reached
    pack = next((p for p in local_packs(server_path) if p["file"] == name), None)
    if pack is None:
        raise ModrinthError("FILE_NOT_FOUND", "There is no such data pack")
    folder = pack_folder(server_path)
    path = folder / name
    if action == "remove":
        if pack["folder"]:
            shutil.rmtree(path)
        else:
            path.unlink()
        return None
    if pack["folder"]:
        raise ModrinthError("INVALID_ACTION", "A data pack folder can only be removed")
    if (action == "disable") == (not pack["enabled"]):
        return name  # already the way it was asked
    new = folder / (
        name[: -len(".disabled")] if not pack["enabled"] else name + ".disabled"
    )
    if new.exists():
        raise ModrinthError("FILE_EXISTS", f"{new.name} is already there")
    path.rename(new)
    return new.name


def search(game_version, query: str = "", offset: int = 0):
    facets = [["project_type:datapack"]]
    if game_version:
        facets.append([f"versions:{game_version}"])
    return modrinth.search_projects(facets, query, offset)


def versions(project_id: str, game_version):
    """The data pack versions of a project for this Minecraft version."""
    found = modrinth.loader_versions(project_id, LOADERS, game_version)
    return [
        modrinth.version_summary(version) for version in found[: modrinth.MAX_VERSIONS]
    ]


def pack_file(version: dict) -> dict:
    """The version's zip: its main file if that is a zip, else its first
    zip (a project can put the mod jar in the same version)."""
    files = version.get("files") or []
    zips = [f for f in files if safe_zip_name(f.get("filename", ""))]
    chosen = next((f for f in zips if f.get("primary")), zips[0] if zips else None)
    if not chosen:
        raise ModrinthError("NO_FILE", "This version has no data pack zip")
    return modrinth.checked_file(chosen)


def _version(project_id: str, game_version, version_id=None) -> dict:
    found = modrinth.loader_versions(project_id, LOADERS, game_version)
    if version_id:
        version = next((v for v in found if v.get("id") == version_id), None)
        if version is None:
            raise ModrinthError(
                "NO_COMPATIBLE_VERSION",
                "This version is not a data pack for this Minecraft version",
            )
        return version
    version = modrinth.pick_version(found, LOADERS)
    if version is None:
        raise ModrinthError(
            "NO_COMPATIBLE_VERSION",
            "This project has no data pack for this Minecraft version",
        )
    return version


def _titles(project_ids):
    """Project names for the message about packs that could not be found."""
    try:
        projects = modrinth.get_projects(project_ids)
    except ModrinthError:
        projects = {}
    return [
        (projects.get(project_id) or {}).get("title") or project_id
        for project_id in project_ids
    ]


def install(server_path, game_version, project_id: str, busy_key: str, version_id=None):
    """Install a data pack, and the data packs it needs that are not there
    yet, into the datapacks folder. A pack that is already there gets the
    new zip and loses the old one (also when it was turned off).

    Returns {"installed": [...], "missing": [names of needed packs
    Modrinth has no data pack for]}.
    """
    if version_id is not None and not modrinth.PROJECT_ID.match(version_id):
        raise ModrinthError("INVALID_VERSION_ID", "Not a Modrinth version")
    with modrinth.only_one(busy_key):
        folder = pack_folder(server_path)
        present = {
            pack["project_id"]: pack
            for pack in installed(server_path, game_version)
            if pack["project_id"]
        }
        done, missing, seen = [], [], set()
        queue = [(project_id, version_id, True)]
        while queue and len(done) < MAX_INSTALLS:
            wanted, wanted_version, main = queue.pop(0)
            if wanted in seen or (not main and wanted in present):
                continue
            seen.add(wanted)
            try:
                version = _version(wanted, game_version, wanted_version)
            except ModrinthError:
                if main:
                    raise
                missing.append(wanted)
                continue
            real_id = version.get("project_id") or wanted
            old = present.get(real_id)
            if old and old.get("version_id") == version.get("id") and old["enabled"]:
                done.append(
                    {
                        "project_id": real_id,
                        "file": old["file"],
                        "version": version.get("version_number"),
                        "replaced": None,
                        "up_to_date": True,
                    }
                )
                continue
            file = pack_file(version)
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / file["filename"]
            modrinth.download(file["url"], target, file["hashes"]["sha512"])
            replaced = old["file"] if old and old["file"] != target.name else None
            if replaced:
                (folder / replaced).unlink(missing_ok=True)
            done.append(
                {
                    "project_id": real_id,
                    "file": target.name,
                    "version": version.get("version_number"),
                    "replaced": replaced,
                    "up_to_date": False,
                }
            )
            for dep in version.get("dependencies") or []:
                dep_id = dep.get("project_id")
                if dep.get("dependency_type") == "required" and dep_id:
                    queue.append((dep_id, None, False))
        return {"installed": done, "missing": _titles(missing)}
