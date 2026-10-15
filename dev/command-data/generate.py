"""Build the command data the Terminal tab uses to suggest commands.

For each Minecraft Java version given, this downloads the official server jar
from Mojang, runs the game's own data generator (``--reports``) and turns its
command tree and ID lists into a small JSON file in
``app/frontend/static/assets/data/commands/``. The Terminal picks the newest
file that is not newer than the server's version.

Usage (needs a Java new enough for each version: 17 for 1.18-1.20.4,
21 for 1.20.5-1.21.11, 25 for 26.1 and later):

    python dev/command-data/generate.py --java /path/to/java 1.21.10 26.3

Downloads and generator output go to a temporary folder unless ``--work`` is
given; pass the same ``--work`` again to reuse earlier downloads.
"""

import argparse
import hashlib
import http.client
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
OUT_DIR = (
    Path(__file__).resolve().parents[2] / "app/frontend/static/assets/data/commands"
)

# Which ID list each argument type suggests from, besides arguments that name
# their registry in their properties.
PARSER_REGISTRY = {
    "item_stack": "item",
    "item_predicate": "item",
    "block_state": "block",
    "block_predicate": "block",
    "particle": "particle_type",
    "entity_summon": "entity_type",
    "mob_effect": "mob_effect",
    "item_enchantment": "enchantment",
}
# Lists longer than this (recipes, loot tables...) are left out to keep the
# file small; items and blocks are always kept.
MAX_LIST = 400
ALWAYS = {"item", "block"}
SKIP_PREFIXES = {"advancement": ("recipes/",)}
# Lists that are not worth their size in suggestions
SKIP_LISTS = {"worldgen/template_pool", "test_instance"}


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def download_server(version: str, work: Path) -> Path:
    jar = work / f"server-{version}.jar"
    manifest = json.loads(fetch(MANIFEST))
    entry = next((v for v in manifest["versions"] if v["id"] == version), None)
    if entry is None:
        sys.exit(f"Unknown Minecraft version {version}")
    info = json.loads(fetch(entry["url"]))
    server = info["downloads"].get("server")
    if not server:
        sys.exit(f"Minecraft {version} has no server download")
    if jar.exists() and hashlib.sha1(jar.read_bytes()).hexdigest() == server["sha1"]:
        return jar
    print(f"Downloading the {version} server jar")
    part = jar.with_suffix(".part")
    part.unlink(missing_ok=True)
    for attempt in range(5):
        # Carry on from where a dropped connection stopped
        done = part.stat().st_size if part.exists() else 0
        request = urllib.request.Request(server["url"])
        if done:
            request.add_header("Range", f"bytes={done}-")
        try:
            with urllib.request.urlopen(request, timeout=120) as response, open(
                part, "ab" if done and response.status == 206 else "wb"
            ) as f:
                shutil.copyfileobj(response, f)
        except (OSError, http.client.HTTPException) as ex:
            print(f"Download interrupted ({ex}), retrying")
            time.sleep(2**attempt)
            continue
        if part.stat().st_size >= server["size"]:
            break
    if hashlib.sha1(part.read_bytes()).hexdigest() != server["sha1"]:
        sys.exit(f"The {version} download is damaged, try again")
    part.replace(jar)
    return jar


def run_generator(java: str, jar: Path, out: Path) -> Path:
    reports = out / "reports"
    if (reports / "commands.json").exists():
        return reports
    with zipfile.ZipFile(jar) as archive:
        bundled = any(n.startswith("META-INF/versions/") for n in archive.namelist())
    if bundled:  # 1.18 and later
        command = [java, "-DbundlerMainClass=net.minecraft.data.Main", "-jar", str(jar)]
    else:
        command = [java, "-cp", str(jar), "net.minecraft.data.Main"]
    command += ["--reports", "--output", str(out)]
    print("Running the data generator")
    env = dict(os.environ)
    # The generator needs no network; keep machine-wide JVM options out of it
    env.pop("JAVA_TOOL_OPTIONS", None)
    subprocess.run(command, cwd=out.parent, check=True, env=env, capture_output=True)
    return reports


def game_files(jar: Path) -> zipfile.ZipFile:
    """The jar holding the game's data folder (nested in newer server jars)."""
    archive = zipfile.ZipFile(jar)
    inner = [
        n
        for n in archive.namelist()
        if n.startswith("META-INF/versions/") and n.endswith(".jar")
    ]
    if inner:
        return zipfile.ZipFile(io.BytesIO(archive.read(inner[0])))
    return archive


def short(name: str) -> str:
    return name[len("minecraft:") :] if name.startswith("minecraft:") else name


def build_tree(commands: dict):
    """Flatten the command tree into a list, sharing identical branches."""
    nodes = []
    seen = {}
    registries = set()

    def add(node: dict, name: str) -> int:
        children = node.get("children", {})
        # Game rules are listed both as "x" and "minecraft:x"; keep one
        names = [
            n
            for n in children
            if not (n.startswith("minecraft:") and short(n) in children)
        ]
        child_ids = [add(children[n], n) for n in names]
        flags = (1 if node["type"] == "argument" else 0) | (
            2 if node.get("executable") else 0
        )
        # [name, flags, children, parser, properties, redirect path]
        entry = [name, flags, child_ids, None, None, None]
        if node["type"] == "argument":
            parser = short(node["parser"])
            props = dict(node.get("properties", {}))
            if "registry" in props:
                props["registry"] = short(props["registry"])
                registries.add(props["registry"])
            elif parser in PARSER_REGISTRY:
                registries.add(PARSER_REGISTRY[parser])
            entry[3] = parser
            entry[4] = props or None
        redirect = node.get("redirect")
        if redirect is None and node["type"] != "root":
            if not children and not node.get("executable"):
                # "execute run": brigadier sends it back to the root, which the
                # report leaves out
                redirect = []
        entry[5] = redirect
        while entry[-1] is None:
            entry.pop()
        key = json.dumps(entry)
        if key not in seen:
            seen[key] = len(nodes)
            nodes.append(entry)
        return seen[key]

    root = add(commands, "")
    return nodes, root, registries


def registry_ids(name: str, reports: Path, game: zipfile.ZipFile, cache: dict):
    if "static" not in cache:
        cache["static"] = json.loads((reports / "registries.json").read_text())
    static = cache["static"].get(f"minecraft:{name}")
    if static:
        ids = [short(i) for i in static["entries"]]
    else:
        # Data-driven lists (enchantments, biomes, structures...) are files
        # in the game's data folder; older versions use plural folder names
        ids = []
        for folder in (name, name + "s"):
            prefix = f"data/minecraft/{folder}/"
            ids = [
                n[len(prefix) : -len(".json")]
                for n in game.namelist()
                if n.startswith(prefix) and n.endswith(".json")
            ]
            if ids:
                break
    skip = SKIP_PREFIXES.get(name, ())
    ids = sorted(i for i in ids if not i.startswith(skip) and i != "air")
    return ids


def generate(version: str, java: str, work: Path) -> Path:
    vdir = work / version
    vdir.mkdir(parents=True, exist_ok=True)
    jar = download_server(version, work)
    reports = run_generator(java, jar, vdir / "generated")
    commands = json.loads((reports / "commands.json").read_text())
    nodes, root, wanted = build_tree(commands)

    game = game_files(jar)
    cache = {}
    lists = {}
    for name in sorted(wanted):
        ids = registry_ids(name, reports, game, cache)
        if name in SKIP_LISTS:
            continue
        if ids and (name in ALWAYS or len(ids) <= MAX_LIST):
            lists[name] = ids

    data = {"version": version, "root": root, "nodes": nodes, "ids": lists}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"java-{version}.json"
    out.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"{out.name}: {len(nodes)} nodes, {out.stat().st_size // 1024} KB")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("versions", nargs="+", help="Minecraft Java versions")
    parser.add_argument("--java", default="java", help="java to run the jar with")
    parser.add_argument("--work", help="folder for downloads (kept)")
    args = parser.parse_args()

    work = Path(args.work) if args.work else Path(tempfile.mkdtemp())
    work.mkdir(parents=True, exist_ok=True)
    try:
        for version in args.versions:
            generate(version, args.java, work)
    finally:
        if not args.work:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
