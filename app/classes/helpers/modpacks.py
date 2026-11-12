"""Make a server from a Modrinth modpack (a .mrpack file).

A modpack is a zip. Its modrinth.index.json names the Minecraft version, the
loader (Fabric, Quilt, Forge or NeoForge) and the files to download, each
with its checksum; overrides/ and then server-overrides/ are copied into the
server as they are (config files and so on). client-overrides/, the files
the pack marks as not for servers, and resource and shader packs are left
out. Running Forge's installer is left to ModdedInstaller.
"""

import json
import logging
import os
import re
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

import requests

from app.classes.helpers import modrinth
from app.classes.helpers.modrinth import ModrinthError

logger = logging.getLogger(__name__)

INDEX = "modrinth.index.json"
# Where a pack's files may come from: Modrinth's own rule for .mrpack files
PACK_HOSTS = (
    "cdn.modrinth.com",
    "github.com",
    "raw.githubusercontent.com",
    "gitlab.com",
)
MAX_PACK_SIZE = 1024**3
MAX_INDEX_SIZE = 16 * 1024 * 1024
MAX_FILES = 2000
MAX_TOTAL_SIZE = 16 * 1024**3
# What overrides/ may unpack to
MAX_OVERRIDE_FILES = 50000
MAX_OVERRIDE_SIZE = 4 * 1024**3
# Room for the loader, its libraries and a first world
SPARE_SPACE = 1024**3
MAX_LOADER_SIZE = 128 * 1024 * 1024
WORKERS = 6
LOADERS = {
    "fabric-loader": "fabric",
    "quilt-loader": "quilt",
    "forge": "forge",
    "neoforge": "neoforge",
}
LOADER_NAMES = {
    "vanilla": "Vanilla",
    "fabric": "Fabric",
    "quilt": "Quilt",
    "forge": "Forge",
    "neoforge": "NeoForge",
}
# Folders only the game itself uses, also when a pack puts files there
CLIENT_FOLDERS = ("resourcepacks", "shaderpacks")
RECORD = "crafty-modpack.json"
LOADER_VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.\-+_]{0,63}$")
SHA512 = re.compile(r"^[0-9a-fA-F]{128}$")
SHA1 = re.compile(r"^[0-9a-fA-F]{40}$")
_JAVA_RELEASE = re.compile(r'^JAVA_VERSION="(?:1\.)?(\d+)', re.M)
# "java-21-openjdk-amd64", "java-1.8.0-openjdk", "jdk-17.0.2+8"
_JAVA_IN_NAME = re.compile(r"(?:^|[-_])(?:1\.)?(\d{1,2})(?=$|[-_.+])")

MOJANG_MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
MOJANG_HOSTS = ("piston-meta.mojang.com", "launchermeta.mojang.com")
MOJANG_DOWNLOAD_HOSTS = ("piston-data.mojang.com", "launcher.mojang.com")
FABRIC_META = "https://meta.fabricmc.net/v2"
QUILT_META = "https://meta.quiltmc.org/v3"
QUILT_HOSTS = ("maven.quiltmc.org",)
QUILT_LAUNCHER = "quilt-server-launch.jar"
FORGE_MAVEN = "https://maven.minecraftforge.net/net/minecraftforge/forge"
NEOFORGE_MAVEN = "https://maven.neoforged.net/releases/net/neoforged"


def safe_path(path):
    """The path if it is a plain relative path ("mods/a.jar"), else None."""
    if not isinstance(path, str) or not path or len(path) > 255:
        return None
    if path.startswith("/") or any(c in path for c in "\\\0:"):
        return None
    if any(part in ("", ".", "..") for part in path.split("/")):
        return None
    return path


def inside(root: Path, path: str) -> Path:
    """root / path, after checking that it stays inside root."""
    base = Path(root).resolve()
    target = (base / path).resolve()
    if base not in target.parents:
        raise ModrinthError("BAD_PACK", "The pack has a file outside the server")
    return target


def _bad(message: str):
    return ModrinthError("BAD_PACK", f"This is not a usable modpack: {message}")


def _pack_file(entry):
    """One entry of the index's file list, checked, or None when a server
    does not need it."""
    if not isinstance(entry, dict):
        raise _bad("a file entry is not readable")
    env = entry.get("env")
    if isinstance(env, dict) and env.get("server") == "unsupported":
        return None
    path = safe_path(entry.get("path"))
    if path is None:
        raise _bad(f"a file has an unsafe path ({str(entry.get('path'))[:100]})")
    if path.split("/")[0] in CLIENT_FOLDERS:
        return None
    hashes = entry.get("hashes") if isinstance(entry.get("hashes"), dict) else {}
    sha512 = hashes.get("sha512")
    if not isinstance(sha512, str) or not SHA512.match(sha512):
        raise _bad(f"{path} has no checksum")
    url = None
    for candidate in entry.get("downloads") or []:
        parsed = urlparse(str(candidate))
        if parsed.scheme == "https" and parsed.hostname in PACK_HOSTS:
            url = str(candidate)
            break
    if url is None:
        raise _bad(f"{path} comes from a site Modrinth does not allow")
    size = entry.get("fileSize", 0)
    if not isinstance(size, int) or size < 0 or size > modrinth.MAX_FILE_SIZE:
        raise _bad(f"{path} is too big")
    return {"path": path, "url": url, "sha512": sha512.lower(), "size": size}


def read_index(archive: zipfile.ZipFile) -> dict:
    """The pack's name, Minecraft version, loader and the files a server
    needs, after checking the index."""
    try:
        info = archive.getinfo(INDEX)
    except KeyError as ex:
        raise ModrinthError(
            "NOT_A_MODPACK", "This is not a Modrinth modpack (no modrinth.index.json)"
        ) from ex
    if info.file_size > MAX_INDEX_SIZE:
        raise _bad("modrinth.index.json is too big")
    try:
        index = json.loads(archive.read(info))
    except (ValueError, zipfile.BadZipFile) as ex:
        raise _bad("modrinth.index.json is not readable") from ex
    if not isinstance(index, dict) or index.get("game") != "minecraft":
        raise _bad("it is not for Minecraft")
    if index.get("formatVersion") != 1:
        raise _bad("it uses a newer format than Crafty knows")
    deps = index.get("dependencies")
    if not isinstance(deps, dict):
        raise _bad("it names no Minecraft version")
    minecraft = deps.get("minecraft")
    if not isinstance(minecraft, str) or not modrinth.GAME_VERSION.match(minecraft):
        raise _bad("it names no Minecraft version")
    found = [(LOADERS[key], value) for key, value in deps.items() if key in LOADERS]
    others = [key for key in deps if key != "minecraft" and key not in LOADERS]
    if others or len(found) > 1:
        raise ModrinthError(
            "UNSUPPORTED_LOADER",
            "This pack needs a loader Crafty cannot set up: "
            + ", ".join(
                str(key)[:40] for key in others or [k for k in deps if k in LOADERS]
            ),
        )
    loader, loader_version = found[0] if found else ("vanilla", None)
    if loader_version is not None and (
        not isinstance(loader_version, str) or not LOADER_VERSION.match(loader_version)
    ):
        raise _bad("the loader version is not readable")
    entries = index.get("files") or []
    if not isinstance(entries, list):
        raise _bad("the file list is not readable")
    files = {}
    skipped = 0
    for entry in entries:
        file = _pack_file(entry)
        if file is None:
            skipped += 1
        else:
            files[file["path"]] = file  # the last one wins, as in a launcher
    if len(files) > MAX_FILES:
        raise ModrinthError("PACK_TOO_BIG", f"The pack has over {MAX_FILES} files")
    size = sum(file["size"] for file in files.values())
    if size > MAX_TOTAL_SIZE:
        raise ModrinthError("PACK_TOO_BIG", "The pack's files are too big")

    def text(key, limit):
        value = index.get(key)
        return value[:limit] if isinstance(value, str) else ""

    return {
        "name": text("name", 100) or "Modpack",
        "version": text("versionId", 100),
        "summary": text("summary", 500),
        "minecraft": minecraft,
        "loader": loader,
        "loader_name": LOADER_NAMES[loader],
        "loader_version": loader_version,
        "files": list(files.values()),
        "file_count": len(files),
        "size": size,
        "skipped": skipped,
    }


def summary(pack_path) -> dict:
    """What the wizard shows about an uploaded pack."""
    try:
        with zipfile.ZipFile(pack_path) as archive:
            pack = read_index(archive)
    except (OSError, zipfile.BadZipFile) as ex:
        raise ModrinthError("NOT_A_MODPACK", "This is not a Modrinth modpack") from ex
    pack.pop("files")
    return pack


def modrinth_pack(project_id: str, version_id: str) -> dict:
    """The .mrpack file of a modpack version on Modrinth, after checks."""
    version = modrinth.get_version(version_id)
    if version.get("project_id") != project_id:
        raise ModrinthError("NOT_FOUND", "This version is not from this modpack")
    files = [
        file
        for file in version.get("files") or []
        if str(file.get("filename", "")).lower().endswith(".mrpack")
    ]
    chosen = next((f for f in files if f.get("primary")), files[0] if files else None)
    if not chosen:
        raise ModrinthError("NO_FILE", "This version has no .mrpack file")
    url = urlparse(str(chosen.get("url", "")))
    if url.scheme != "https" or url.hostname not in modrinth.DOWNLOAD_HOSTS:
        raise ModrinthError("BAD_FILE", "The file is not on Modrinth's servers")
    sha512 = (chosen.get("hashes") or {}).get("sha512")
    if not isinstance(sha512, str) or not SHA512.match(sha512):
        raise ModrinthError("BAD_FILE", "Modrinth gave no checksum for the file")
    if int(chosen.get("size") or 0) > MAX_PACK_SIZE:
        raise ModrinthError("FILE_TOO_BIG", "The pack is bigger than 1 GB")
    return {"url": chosen["url"], "sha512": sha512, "version": version}


def check_space(root, pack: dict) -> None:
    need = pack["size"] + SPARE_SPACE
    if shutil.disk_usage(root).free < need:
        raise ModrinthError(
            "NO_SPACE",
            f"Not enough free disk space: the pack needs about "
            f"{need / 1024**3:.1f} GB",
        )


def _download_one(file: dict, root: Path) -> None:
    target = inside(root, file["path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        modrinth.download(file["url"], target, file["sha512"])
    except ModrinthError as ex:
        if ex.code != "DOWNLOAD_FAILED":
            raise ModrinthError(ex.code, f"{file['path']}: {ex}") from ex
        try:  # once more: one failed file should not stop a big pack
            modrinth.download(file["url"], target, file["sha512"])
        except ModrinthError as again:
            raise ModrinthError(again.code, f"{file['path']}: {again}") from again


def download_files(files: list, root: Path, progress=None) -> None:
    """Download the pack's files into the server, a few at a time.
    progress(done, total) is called after each one."""
    pool = ThreadPoolExecutor(max_workers=WORKERS)
    try:
        futures = [pool.submit(_download_one, file, root) for file in files]
        for done, future in enumerate(as_completed(futures), start=1):
            future.result()
            if progress:
                progress(done, len(files))
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


def copy_overrides(archive: zipfile.ZipFile, root: Path) -> int:
    """Copy overrides/, then server-overrides/ (which wins), into the server.
    Returns how many files were copied."""
    count = size = 0
    for prefix in ("overrides/", "server-overrides/"):
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            if not name.startswith(prefix) or name.endswith("/"):
                continue
            path = safe_path(name[len(prefix) :])
            if path is None:
                raise _bad(f"a file has an unsafe path ({name[:100]})")
            if path.split("/")[0] in CLIENT_FOLDERS:
                continue
            count += 1
            size += info.file_size
            if count > MAX_OVERRIDE_FILES or size > MAX_OVERRIDE_SIZE:
                raise ModrinthError("PACK_TOO_BIG", "The pack's files are too big")
            target = inside(root, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, open(target, "wb") as dest:
                shutil.copyfileobj(source, dest, 1024 * 1024)
    return count


def set_property(path: Path, key: str, value) -> None:
    """Set one key in a .properties file, keeping the other lines."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        lines = []
    wanted = f"{key}={value}"
    found = False
    for number, line in enumerate(lines):
        if not line.lstrip().startswith(("#", "!")) and (
            line.split("=", 1)[0].strip() == key
        ):
            lines[number] = wanted
            found = True
    if not found:
        lines.append(wanted)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def java_major(path: str):
    """The Java version (8, 17, 21, ...) of a java program, from the release
    file of its Java, else from its folder's name; None when unknown."""
    exe = Path(path)
    for home in (exe.parent.parent, exe.parent.parent.parent):  # jre/bin/java
        try:
            text = (home / "release").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        found = _JAVA_RELEASE.search(text)
        if found:
            return int(found.group(1))
    for part in exe.parts:
        found = _JAVA_IN_NAME.search(part)
        if found:
            return int(found.group(1))
    return None


def required_java(minecraft: str, info=None) -> int:
    """The Java a Minecraft version needs: Mojang's answer when there is one."""
    major = ((info or {}).get("javaVersion") or {}).get("majorVersion")
    if isinstance(major, int) and major > 0:
        return major
    numbers = [int(n) for n in re.findall(r"\d+", minecraft)]
    snapshot = re.match(r"^(\d\d)w\d\d", minecraft)
    if snapshot:
        year = int(snapshot.group(1))
        return 21 if year >= 24 else 17 if year >= 21 else 8
    if not numbers or numbers[0] >= 25:
        return 25
    minor, patch = (numbers[1:] + [0, 0])[:2]
    if (minor, patch) >= (20, 5):
        return 21
    if minor >= 18:
        return 17
    return 16 if minor == 17 else 8


def pick_java(required: int, installs) -> tuple:
    """The java to run the server with: the oldest installed Java that is new
    enough (old Forge does not start on newer ones), else plain "java".
    Returns (path or "java", its version or None)."""
    found = []
    if os.name != "nt":  # Windows lists Java folders; "java" is used there
        for path in installs or []:
            path = str(path).strip()
            major = java_major(path) if path else None
            if major and major >= required:
                found.append((major, path))
    if not found:
        return "java", None
    major, path = min(found)
    return path, major


def java_word(java: str) -> str:
    """java as the first word of a start command."""
    return "java" if java == "java" else f'"{java}"'


def _get_json(url: str):
    try:
        response = requests.get(
            url, headers={"User-Agent": modrinth.USER_AGENT}, timeout=modrinth.TIMEOUT
        )
    except OSError as ex:  # requests' errors are OSErrors too
        host = urlparse(url).hostname
        raise ModrinthError("LOADER_FAILED", f"{host}: {ex}") from ex
    if response.status_code != 200:
        raise ModrinthError(
            "LOADER_FAILED",
            f"{urlparse(url).hostname} answered {response.status_code}",
        )
    try:
        return response.json()
    except ValueError as ex:
        raise ModrinthError(
            "LOADER_FAILED", f"{urlparse(url).hostname} sent an unreadable answer"
        ) from ex


def _https_on(url, hosts) -> bool:
    parsed = urlparse(str(url or ""))
    return parsed.scheme == "https" and parsed.hostname in hosts


def minecraft_info(minecraft: str) -> dict:
    """Mojang's details of a Minecraft version (its Java, its server jar)."""
    manifest = _get_json(MOJANG_MANIFEST)
    entry = next(
        (v for v in manifest.get("versions", []) if v.get("id") == minecraft), None
    )
    if entry is None:
        raise ModrinthError(
            "UNKNOWN_VERSION", f"Mojang does not know Minecraft {minecraft}"
        )
    if not _https_on(entry.get("url"), MOJANG_HOSTS):
        raise ModrinthError("LOADER_FAILED", "Mojang's version list is not usable")
    return _get_json(entry["url"])


def setup_vanilla(root: Path, info: dict) -> str:
    server = (info.get("downloads") or {}).get("server") or {}
    sha1 = server.get("sha1")
    if not _https_on(server.get("url"), MOJANG_DOWNLOAD_HOSTS) or not (
        isinstance(sha1, str) and SHA1.match(sha1)
    ):
        raise ModrinthError("LOADER_FAILED", "Mojang has no server for this version")
    modrinth.download(
        server["url"], root / "server.jar", sha1=sha1, max_size=MAX_LOADER_SIZE
    )
    return "server.jar"


def setup_fabric(root: Path, minecraft: str, loader_version: str) -> str:
    """Fabric's server launcher, which fetches the rest on its first start."""
    installers = _get_json(f"{FABRIC_META}/versions/installer")
    installer = next(
        (i.get("version") for i in installers if i.get("stable")),
        None,
    )
    if not isinstance(installer, str) or not LOADER_VERSION.match(installer):
        raise ModrinthError("LOADER_FAILED", "Fabric's installer list is not usable")
    name = (
        f"fabric-server-mc.{minecraft}-loader.{loader_version}"
        f"-launcher.{installer}.jar"
    )
    url = (
        f"{FABRIC_META}/versions/loader/{quote(minecraft, safe='')}/"
        f"{quote(loader_version, safe='')}/{quote(installer, safe='')}/server/jar"
    )
    modrinth.download(url, root / name, max_size=MAX_LOADER_SIZE)
    return name


def _version_key(version: str):
    return [int(n) for n in re.findall(r"\d+", version or "")]


def setup_quilt(root: Path, minecraft: str, loader_version: str, java, run) -> str:
    """Run Quilt's installer; run(args) runs a program in the server folder
    and returns its exit code."""
    installers = [
        i
        for i in _get_json(f"{QUILT_META}/versions/installer")
        if _https_on(i.get("url"), QUILT_HOSTS)
    ]
    if not installers:
        raise ModrinthError("LOADER_FAILED", "Quilt's installer list is not usable")
    newest = max(installers, key=lambda i: _version_key(i.get("version")))
    sha512 = (newest.get("hashes") or {}).get("sha512")
    name = ".quilt-installer.jar"
    modrinth.download(
        newest["url"],
        root / name,
        sha512 if isinstance(sha512, str) and SHA512.match(sha512) else None,
        max_size=MAX_LOADER_SIZE,
    )
    try:
        code = run(
            [
                java,
                "-jar",
                name,
                "install",
                "server",
                minecraft,
                loader_version,
                "--download-server",
                f"--install-dir={Path(root).resolve()}",
            ]
        )
    finally:
        (root / name).unlink(missing_ok=True)
    if code != 0 or not (root / QUILT_LAUNCHER).is_file():
        raise ModrinthError(
            "LOADER_FAILED", "Quilt's installer failed; see the server's Terminal"
        )
    return QUILT_LAUNCHER


def forge_installer_urls(loader: str, minecraft: str, loader_version: str):
    if loader == "forge":
        # Very old versions repeat the Minecraft version at the end
        names = [f"{minecraft}-{loader_version}"]
        names.append(f"{names[0]}-{minecraft}")
        return [f"{FORGE_MAVEN}/{n}/forge-{n}-installer.jar" for n in names]
    if minecraft == "1.20.1":  # NeoForge's first version kept Forge's names
        version = loader_version.removeprefix("1.20.1-")
        name = f"1.20.1-{version}"
        return [f"{NEOFORGE_MAVEN}/forge/{name}/forge-{name}-installer.jar"]
    return [
        f"{NEOFORGE_MAVEN}/neoforge/{loader_version}/"
        f"neoforge-{loader_version}-installer.jar"
    ]


def _maven_sha1(url: str):
    """The checksum a Maven repository keeps next to a file, if it has one."""
    try:
        response = requests.get(
            f"{url}.sha1",
            headers={"User-Agent": modrinth.USER_AGENT},
            timeout=modrinth.TIMEOUT,
        )
    except OSError:
        return None
    text = response.text.strip()[:40] if response.status_code == 200 else ""
    return text if SHA1.match(text) else None


def get_forge_installer(root: Path, loader: str, minecraft: str, version: str):
    """Download Forge's or NeoForge's installer under the name
    ModdedInstaller reads the Minecraft version from."""
    name = f"{loader}-installer-{minecraft}.jar"
    problem = None
    for url in forge_installer_urls(loader, minecraft, version):
        try:
            modrinth.download(
                url, root / name, sha1=_maven_sha1(url), max_size=MAX_LOADER_SIZE
            )
            return name
        except ModrinthError as ex:
            problem = ex
    raise ModrinthError(
        "LOADER_FAILED",
        f"Could not download {LOADER_NAMES[loader]} {version}: {problem}",
    )


def write_record(root: Path, pack: dict, source: dict) -> None:
    """What was installed, for a later update of the pack."""
    record = {
        "source": source,
        "name": pack["name"],
        "version": pack["version"],
        "minecraft": pack["minecraft"],
        "loader": pack["loader"],
        "loader_version": pack["loader_version"],
        "installed": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": sorted(file["path"] for file in pack["files"]),
    }
    (root / RECORD).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def build(root, pack_path, options: dict, say, run) -> dict:
    """Make a server in root from a .mrpack file.

    options: mem_min and mem_max (GB), port, agree_to_eula, java_installs
    (paths) and source (kept in the record). say(text) reports progress;
    run(args) runs a program in root and returns its exit code.

    Returns {"executable", "command", "installer"}: with installer True the
    command runs Forge's or NeoForge's installer, which the caller runs.
    """
    root = Path(root)
    with zipfile.ZipFile(pack_path) as archive:
        pack = read_index(archive)
        loader = pack["loader"]
        say(
            f"{pack['name']} {pack['version']}: Minecraft {pack['minecraft']}, "
            f"{pack['loader_name']} {pack['loader_version'] or ''}".rstrip()
        )
        info = minecraft_info(pack["minecraft"])
        required = required_java(pack["minecraft"], info)
        java, major = pick_java(required, options.get("java_installs"))
        if major:
            say(f"Java {major} will run the server (Java {required} or newer needed)")
        else:
            say(f"Java {required} or newer is needed; the server will use 'java'")
        check_space(root, pack)
        total = len(pack["files"])
        say(f"Downloading {total} files ({pack['size'] / 1024**2:.0f} MB)")

        def progress(done, count):
            # About one line for each tenth of the files
            if done == count or done * 10 // count > (done - 1) * 10 // count:
                say(f"Downloaded {done} of {count} files")

        download_files(pack["files"], root, progress)
        if pack["skipped"]:
            say(f"Left out {pack['skipped']} files only players need")
        copied = copy_overrides(archive, root)
        if copied:
            say(f"Copied {copied} config and other files from the pack")
    # The pack may bring its own; the wizard's choices win
    set_property(root / "server.properties", "server-port", int(options["port"]))
    eula = "true" if options.get("agree_to_eula") else "false"
    (root / "eula.txt").write_text(f"eula={eula}\n", encoding="utf-8")
    write_record(root, pack, options.get("source") or {})

    # GB from the wizard to whole MiB, as for other new servers
    memory = (
        f"-Xms{round(float(options['mem_min']) * 1024)}M "
        f"-Xmx{round(float(options['mem_max']) * 1024)}M"
    )
    say(f"Setting up {pack['loader_name']}")
    if loader in ("forge", "neoforge"):
        name = get_forge_installer(
            root, loader, pack["minecraft"], pack["loader_version"]
        )
        return {
            "executable": name,
            "command": f"{java_word(java)} {memory} -jar {name} --installServer",
            "installer": True,
        }
    if loader == "fabric":
        jar = setup_fabric(root, pack["minecraft"], pack["loader_version"])
    elif loader == "quilt":
        jar = setup_quilt(root, pack["minecraft"], pack["loader_version"], java, run)
    else:
        jar = setup_vanilla(root, info)
    return {
        "executable": jar,
        "command": f"{java_word(java)} {memory} -jar {jar} nogui",
        "installer": False,
    }
