"""Find mods and plugins on Modrinth (modrinth.com) and install them.

Works out what a server can load (Paper plugins, Fabric mods, ...) and its
Minecraft version, searches Modrinth for matching projects, and downloads
the right file, with the projects it needs, into the server's plugins or
mods folder. Installing a project that is already there replaces its file,
so the same call updates it.
"""

import hashlib
import json
import logging
import os
import re
import threading
from pathlib import Path
from urllib.parse import quote, urlparse

import requests

logger = logging.getLogger(__name__)

API = "https://api.modrinth.com/v2"
USER_AGENT = "GiorgosPap777/Better-Crafty (github.com/GiorgosPap777/Better-Crafty)"
DOWNLOAD_HOSTS = ("cdn.modrinth.com",)
TIMEOUT = 20
MAX_FILE_SIZE = 256 * 1024 * 1024
# A project, its dependencies and theirs: enough for real mods, and a limit
# for a broken dependency list
MAX_INSTALLS = 12
# How many versions of a project the version list shows
MAX_VERSIONS = 50

# What each kind of server loads, as Modrinth loader names, best first
PLATFORMS = {
    "paper": ("plugins", ["paper", "spigot", "bukkit"]),
    "purpur": ("plugins", ["purpur", "paper", "spigot", "bukkit"]),
    "folia": ("plugins", ["folia"]),
    "spigot": ("plugins", ["spigot", "bukkit"]),
    "bukkit": ("plugins", ["bukkit"]),
    "velocity": ("plugins", ["velocity"]),
    "waterfall": ("plugins", ["waterfall", "bungeecord"]),
    "bungeecord": ("plugins", ["bungeecord"]),
    "fabric": ("mods", ["fabric"]),
    "quilt": ("mods", ["quilt", "fabric"]),
    "neoforge": ("mods", ["neoforge"]),
    "forge": ("mods", ["forge"]),
}
# Proxies run plugins for any Minecraft version
PROXIES = ("velocity", "waterfall", "bungeecord")
PLATFORM_NAMES = {
    "paper": "Paper",
    "purpur": "Purpur",
    "folia": "Folia",
    "spigot": "Spigot",
    "bukkit": "Bukkit",
    "velocity": "Velocity",
    "waterfall": "Waterfall",
    "bungeecord": "BungeeCord",
    "fabric": "Fabric",
    "quilt": "Quilt",
    "neoforge": "NeoForge",
    "forge": "Forge",
}
# Words in the jar name or the start command, checked in this order
# ("neoforge" before "forge", "purpur" and "folia" before "paper")
NAME_HINTS = (
    "neoforge",
    "forge",
    "quilt",
    "fabric",
    "purpur",
    "folia",
    "paper",
    "waterfall",
    "velocity",
    "bungeecord",
    "spigot",
    "bukkit",
)
# Files a server leaves behind, for jars with a plain name like server.jar
FILE_HINTS = (
    # The loaders themselves: Paper keeps other NeoForged tools in libraries/
    ("libraries/net/neoforged/neoforge", "neoforge"),
    ("libraries/net/minecraftforge/forge", "forge"),
    (".quilt", "quilt"),
    ("quilt-server-launch.jar", "quilt"),
    (".fabric", "fabric"),
    ("fabric-server-launch.jar", "fabric"),
    ("fabric-server-launcher.properties", "fabric"),
    ("purpur.yml", "purpur"),
    ("config/paper-global.yml", "paper"),
    ("paper.yml", "paper"),
    ("velocity.toml", "velocity"),
    ("spigot.yml", "spigot"),
    ("bukkit.yml", "bukkit"),
)
DISABLED = ".jar.disabled"
JAR_ACTIONS = ("enable", "disable", "remove")
GAME_VERSION = re.compile(r"^[0-9][0-9A-Za-z.\-+]{0,31}$")
PROJECT_ID = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
# Minecraft versions: 1.8 to 1.21.x, and the year numbers from 26.1 on
_MC_VERSION = re.compile(
    r"(?<!\d)(?<!\d\.)"
    r"(1\.(?:[7-9]|[1-9]\d)(?:\.\d{1,2})?|2[5-9]\.\d{1,2}(?:\.\d{1,2})?)"
    r"(?!\d)(?!\.\d)"
)
_PAPER_HISTORY = re.compile(r"MC: ([0-9][0-9.]*)")
_NEOFORGE_LIBRARY = re.compile(r"neoforge[/-](\d{2})\.(\d{1,2})\.\d")

_busy = set()
_busy_lock = threading.Lock()


class ModrinthError(Exception):
    """A request that cannot be done; code is a short name for the API."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def detect_platform(server_path, executable: str = "", command: str = ""):
    """The PLATFORMS key for the server, or None (vanilla, Bedrock, ...)."""
    words = f"{executable} {command}".lower()
    for name in NAME_HINTS:
        if name in words:
            return name
    path = Path(server_path)
    for marker, name in FILE_HINTS:
        if (path / marker).exists():
            return name
    return None


def detect_game_version(
    server_path, stats_version: str = "", executable: str = "", command: str = ""
):
    """The server's Minecraft version, e.g. "1.21.4" or "26.1", or None."""
    try:
        history = json.loads(
            (Path(server_path) / "version_history.json").read_text(encoding="utf-8")
        )
        found = _PAPER_HISTORY.search(str(history.get("currentVersion", "")))
        if found:
            return found.group(1).rstrip(".")
    except (OSError, ValueError, AttributeError):
        pass
    for text in (stats_version or "", f"{executable} {command}"):
        found = _MC_VERSION.search(text)
        if found:
            return found.group(1)
    # NeoForge's own version tells the Minecraft one: 21.1.x is 1.21.1. It is
    # in Crafty's start command, else in the name of its library folder.
    texts = [command or ""]
    try:
        library = Path(server_path) / "libraries" / "net" / "neoforged" / "neoforge"
        texts += sorted(f"neoforge/{path.name}" for path in library.iterdir())[-1:]
    except OSError:
        pass
    for text in texts:
        found = _NEOFORGE_LIBRARY.search(text)
        if found and int(found.group(1)) < 25:
            minor = int(found.group(2))
            return f"1.{found.group(1)}" + (f".{minor}" if minor else "")
    return None


def platform_info(platform, game_version):
    """What the page shows about what can be installed on this server."""
    if platform not in PLATFORMS:
        return {"supported": False}
    folder, loaders = PLATFORMS[platform]
    return {
        "supported": True,
        "platform": platform,
        "platform_name": PLATFORM_NAMES[platform],
        "folder": folder,
        "kind": "plugin" if folder == "plugins" else "mod",
        "loaders": loaders,
        "game_version": None if platform in PROXIES else game_version,
        "needs_game_version": platform not in PROXIES,
    }


def _get(url: str, **params):
    try:
        response = requests.get(
            url,
            params=params or None,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
    except OSError as ex:  # requests' errors are OSErrors too
        raise ModrinthError("MODRINTH_UNREACHABLE", f"Modrinth: {ex}") from ex
    if response.status_code == 404:
        raise ModrinthError("NOT_FOUND", "Modrinth does not know this project")
    if response.status_code != 200:
        raise ModrinthError(
            "MODRINTH_ERROR", f"Modrinth answered {response.status_code}"
        )
    try:
        return response.json()
    except ValueError as ex:
        raise ModrinthError(
            "MODRINTH_ERROR", "Modrinth sent an unreadable answer"
        ) from ex


def _post(url: str, body: dict):
    try:
        response = requests.post(
            url, json=body, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT
        )
        if response.status_code != 200:
            raise ModrinthError(
                "MODRINTH_ERROR", f"Modrinth answered {response.status_code}"
            )
        return response.json()
    except OSError as ex:  # requests' errors are OSErrors too
        raise ModrinthError("MODRINTH_UNREACHABLE", f"Modrinth: {ex}") from ex
    except ValueError as ex:
        raise ModrinthError(
            "MODRINTH_ERROR", "Modrinth sent an unreadable answer"
        ) from ex


def search_facets(platform: str, game_version):
    folder, loaders = PLATFORMS[platform]
    facets = [
        [f"categories:{loader}" for loader in loaders],
        ["project_type:plugin" if folder == "plugins" else "project_type:mod"],
    ]
    if game_version and platform not in PROXIES:
        facets.append([f"versions:{game_version}"])
    if folder == "mods":
        # Mods that only change the game's screen do nothing on a server
        facets.append(["server_side!=unsupported"])
    return facets


def search(platform: str, game_version, query: str = "", offset: int = 0):
    """One page (20) of matching projects, most relevant first, or most
    downloaded when there is no search text."""
    data = _get(
        f"{API}/search",
        query=query[:100],
        facets=json.dumps(search_facets(platform, game_version)),
        index="relevance" if query.strip() else "downloads",
        offset=max(0, min(int(offset), 10000)),
        limit=20,
    )
    hits = [
        {
            "project_id": hit.get("project_id"),
            "slug": hit.get("slug"),
            "title": hit.get("title"),
            "description": hit.get("description"),
            "author": hit.get("author"),
            "icon_url": hit.get("icon_url") or None,
            "downloads": hit.get("downloads", 0),
            "categories": hit.get("display_categories") or hit.get("categories", []),
            "date_modified": hit.get("date_modified"),
        }
        for hit in data.get("hits", [])
    ]
    return {
        "hits": hits,
        "offset": data.get("offset", 0),
        "total": data.get("total_hits", 0),
    }


def pick_version(versions, loaders):
    """The newest release (else the newest beta, else alpha) for the best
    loader the server has, from Modrinth's newest-first list."""
    for wanted in ("release", "beta", "alpha"):
        for loader in loaders:
            for version in versions:
                if version.get("version_type") == wanted and loader in version.get(
                    "loaders", []
                ):
                    return version
    return None


def project_versions(project_id: str, platform: str, game_version):
    if not PROJECT_ID.match(project_id or ""):
        raise ModrinthError("INVALID_PROJECT", "Not a Modrinth project")
    loaders = PLATFORMS[platform][1]
    params = {"loaders": json.dumps(loaders)}
    if game_version and platform not in PROXIES:
        params["game_versions"] = json.dumps([game_version])
    return _get(f"{API}/project/{quote(project_id, safe='')}/version", **params)


def best_version(project_id: str, platform: str, game_version):
    version = pick_version(
        project_versions(project_id, platform, game_version), PLATFORMS[platform][1]
    )
    if version is None:
        raise ModrinthError(
            "NO_COMPATIBLE_VERSION",
            "This project has no file for this server's loader and version",
        )
    return version


def chosen_version(project_id: str, platform: str, game_version, version_id: str):
    """The version the user picked, if it is one this server can load."""
    for version in project_versions(project_id, platform, game_version):
        if version.get("id") == version_id:
            return version
    raise ModrinthError(
        "NO_COMPATIBLE_VERSION",
        "This version is not for this server's loader and version",
    )


def versions(project_id: str, platform: str, game_version):
    """The versions of a project this server can load, newest first."""
    return [
        {
            "id": version.get("id"),
            "version_number": version.get("version_number"),
            "name": version.get("name"),
            "version_type": version.get("version_type"),
            "date_published": version.get("date_published"),
            "game_versions": version.get("game_versions") or [],
            "loaders": version.get("loaders") or [],
        }
        for version in project_versions(project_id, platform, game_version)[
            :MAX_VERSIONS
        ]
    ]


def primary_file(version: dict) -> dict:
    """The version's main jar, after checking where it comes from and its
    name."""
    files = version.get("files") or []
    chosen = next((f for f in files if f.get("primary")), files[0] if files else None)
    if not chosen:
        raise ModrinthError("NO_FILE", "This version has no file")
    url = urlparse(str(chosen.get("url", "")))
    if url.scheme != "https" or url.hostname not in DOWNLOAD_HOSTS:
        raise ModrinthError("BAD_FILE", "The file is not on Modrinth's servers")
    if not safe_jar_name(chosen.get("filename", "")):
        raise ModrinthError("BAD_FILE", "The file does not have a usable jar name")
    if not (chosen.get("hashes") or {}).get("sha512"):
        raise ModrinthError("BAD_FILE", "Modrinth gave no checksum for the file")
    if int(chosen.get("size") or 0) > MAX_FILE_SIZE:
        raise ModrinthError("FILE_TOO_BIG", "The file is bigger than 256 MB")
    return chosen


def safe_jar_name(name: str) -> bool:
    return (
        isinstance(name, str)
        and 4 < len(name) <= 200
        and name.lower().endswith(".jar")
        and not name.startswith(".")
        and os.path.basename(name) == name
        and not any(c in name for c in "/\\\0:")
    )


def jar_folder(server_path, platform: str) -> Path:
    base = Path(server_path).resolve()
    folder = (base / PLATFORMS[platform][0]).resolve()
    if folder.parent != base:
        raise ModrinthError(
            "BAD_FOLDER", "The plugins or mods folder is outside the server"
        )
    return folder


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_jars(server_path, platform: str):
    """The jars in the plugins or mods folder, also the turned off ones
    (.jar.disabled), without asking Modrinth."""
    folder = jar_folder(server_path, platform)
    jars = []
    if folder.is_dir():
        for path in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
            name = path.name
            enabled = name.lower().endswith(".jar")
            if not path.is_file() or not (enabled or name.lower().endswith(DISABLED)):
                continue
            jars.append(
                {
                    "file": name,
                    "size": path.stat().st_size,
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
    return jars


def change_jar(server_path, platform: str, name: str, action: str):
    """Turn a jar off (rename it to .jar.disabled), on again, or remove it.
    Returns the jar's new name, or None when it was removed."""
    if action not in JAR_ACTIONS:
        raise ModrinthError("INVALID_ACTION", "action: enable, disable or remove")
    # Only names that are in the folder: nothing else can be reached
    if name not in {jar["file"] for jar in local_jars(server_path, platform)}:
        raise ModrinthError("FILE_NOT_FOUND", "There is no such jar in the folder")
    folder = jar_folder(server_path, platform)
    path = folder / name
    if action == "remove":
        path.unlink()
        return None
    disabled = name.lower().endswith(DISABLED)
    if (action == "disable") == disabled:
        return name  # already the way it was asked
    # a.jar <-> a.jar.disabled
    new = folder / (name[: -len(".disabled")] if disabled else name + ".disabled")
    if new.exists():
        raise ModrinthError("FILE_EXISTS", f"{new.name} is already there")
    path.rename(new)
    return new.name


def installed(server_path, platform: str, game_version=None):
    """The jars in the plugins or mods folder, with the Modrinth project each
    one belongs to (None for jars from elsewhere) and whether Modrinth has a
    newer file for this server."""
    folder = jar_folder(server_path, platform)
    jars = local_jars(server_path, platform)
    for jar in jars:
        jar["sha1"] = _sha1(folder / jar["file"])
    if not jars:
        return []
    hashes = [jar["sha1"] for jar in jars]
    known = _post(f"{API}/version_files", {"hashes": hashes, "algorithm": "sha1"})
    loaders = PLATFORMS[platform][1]
    updates = {}
    if known:
        body = {"hashes": list(known), "algorithm": "sha1", "loaders": loaders}
        if game_version and platform not in PROXIES:
            body["game_versions"] = [game_version]
        updates = _post(f"{API}/version_files/update", body) or {}
    projects = {}
    ids = sorted({v.get("project_id") for v in known.values() if v.get("project_id")})
    if ids:
        for project in _get(f"{API}/projects", ids=json.dumps(ids)):
            projects[project.get("id")] = project
    for jar in jars:
        version = known.get(jar["sha1"])
        jar["project_id"] = version.get("project_id") if version else None
        project = projects.get(jar["project_id"], {})
        jar["title"] = project.get("title")
        jar["slug"] = project.get("slug")
        jar["icon_url"] = project.get("icon_url") or None
        jar["version"] = version.get("version_number") if version else None
        jar["version_id"] = version.get("id") if version else None
        newer = updates.get(jar["sha1"])
        jar["update"] = (
            newer.get("version_number")
            if version and newer and newer.get("id") != version.get("id")
            else None
        )
    return jars


def _download(url: str, target: Path, sha512: str) -> None:
    """Download to a hidden file next to the target, check the size and the
    checksum, then move it into place."""
    part = target.with_name(f".{target.name}.part")
    digest = hashlib.sha512()
    size = 0
    try:
        with requests.get(
            url, stream=True, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT
        ) as response:
            if response.status_code != 200:
                raise ModrinthError(
                    "DOWNLOAD_FAILED", f"The download answered {response.status_code}"
                )
            # A new file, never one a link in the folder points to
            part.unlink(missing_ok=True)
            with open(part, "xb") as f:
                for chunk in response.iter_content(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_FILE_SIZE:
                        raise ModrinthError(
                            "FILE_TOO_BIG", "The file is bigger than 256 MB"
                        )
                    digest.update(chunk)
                    f.write(chunk)
        if digest.hexdigest() != sha512.lower():
            raise ModrinthError("BAD_CHECKSUM", "The downloaded file is damaged")
        os.replace(part, target)
    except OSError as ex:  # requests' errors are OSErrors too
        raise ModrinthError("DOWNLOAD_FAILED", f"Download: {ex}") from ex
    finally:
        part.unlink(missing_ok=True)


def install(
    server_path,
    platform: str,
    game_version,
    project_id: str,
    busy_key: str,
    version_id=None,
):
    """Install a project and the projects it needs that are not there yet.
    A project already in the folder gets the new file and loses the old one.
    version_id picks a version of the project instead of the newest.

    Returns {"installed": [...], "missing": [...]}; missing lists required
    projects Modrinth has no file for on this server.
    """
    if version_id is not None and not PROJECT_ID.match(version_id):
        raise ModrinthError("INVALID_VERSION_ID", "Not a Modrinth version")
    with _busy_lock:
        if busy_key in _busy:
            raise ModrinthError("BUSY", "Another install for this server is running")
        _busy.add(busy_key)
    try:
        folder = jar_folder(server_path, platform)
        present = {
            jar["project_id"]: jar
            for jar in installed(server_path, platform, game_version)
            if jar["project_id"]
        }
        done, missing = [], []
        queue = [(project_id, version_id, True)]
        seen = set()
        while queue and len(done) < MAX_INSTALLS:
            wanted, version_id, main = queue.pop(0)
            if wanted in seen or (not main and wanted in present):
                continue
            seen.add(wanted)
            try:
                if not version_id or not PROJECT_ID.match(version_id):
                    version = best_version(wanted, platform, game_version)
                elif main:
                    version = chosen_version(wanted, platform, game_version, version_id)
                else:
                    version = _get(f"{API}/version/{quote(version_id, safe='')}")
            except ModrinthError:
                if main:
                    raise
                missing.append(wanted)
                continue
            real_id = version.get("project_id") or wanted
            if not main and real_id != wanted and real_id in seen:
                continue
            seen.add(real_id)
            old = present.get(real_id)
            if not main and old:
                continue  # a dependency that is already there
            if old and old.get("version_id") == version.get("id"):
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
            file = primary_file(version)
            folder.mkdir(exist_ok=True)
            target = folder / file["filename"]
            _download(file["url"], target, file["hashes"]["sha512"])
            if old and old["file"] != target.name:
                (folder / old["file"]).unlink(missing_ok=True)
            done.append(
                {
                    "project_id": real_id,
                    "file": target.name,
                    "version": version.get("version_number"),
                    "replaced": (
                        old["file"] if old and old["file"] != target.name else None
                    ),
                    "up_to_date": False,
                }
            )
            for dep in version.get("dependencies") or []:
                dep_id = dep.get("project_id")
                if dep.get("dependency_type") == "required" and dep_id:
                    queue.append((dep_id, dep.get("version_id"), False))
        return {"installed": done, "missing": missing}
    finally:
        with _busy_lock:
            _busy.discard(busy_key)
