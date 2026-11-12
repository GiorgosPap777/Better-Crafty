"""Which servers have mod, plugin or data pack updates on Modrinth.

Crafty checks every Minecraft Java server every few hours, and the Mods tab
refreshes a server's entry whenever it lists the files. The result is kept
in ``app/config/db/servers/<id>/mod_updates.json``, so the dashboard can
show a badge without asking Modrinth, and it is still there after a
restart. The same file remembers the server type and Minecraft version
chosen on the Mods tab when Crafty could not find them.

Only files that are turned on count: an update would turn a turned off
file back on.
"""

import datetime
import json
import logging
import os
import time
from pathlib import Path

from app.classes.helpers import datapacks, modrinth

logger = logging.getLogger(__name__)

STATE_FILE = "mod_updates.json"
CHECK_HOURS = 6
# Between two servers, to go easy on Modrinth
PAUSE_SECONDS = 2
# Names in the badge's tooltip
MAX_NAMES = 50


def _state_path(root_dir, server_id) -> Path:
    return Path(root_dir, "app", "config", "db", "servers", str(server_id), STATE_FILE)


def get(root_dir, server_id) -> dict:
    """What was found the last time (an empty dict when never checked)."""
    try:
        with open(_state_path(root_dir, server_id), encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def _save(root_dir, server_id, state: dict) -> None:
    path = _state_path(root_dir, server_id)
    if not path.parent.is_dir():
        return  # the server is gone
    part = path.with_name(f".{path.name}.part")
    try:
        with open(part, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(part, path)
    except OSError as ex:
        logger.warning(f"Could not save the mod updates of {server_id}: {ex}")
        part.unlink(missing_ok=True)


def outdated(items) -> list:
    """The files (turned on, from Modrinth) that have a newer version."""
    return [
        {
            "file": item["file"],
            "title": item.get("title") or item["file"],
            "project_id": item["project_id"],
            "version": item.get("version"),
            "update": item["update"],
        }
        for item in items or []
        if item.get("update") and item.get("project_id") and item.get("enabled")
    ]


def count(state: dict) -> int:
    return len(state.get("mods") or []) + len(state.get("packs") or [])


def names(state: dict) -> list:
    """ "Name (old → new)" for each update, for the badge's tooltip."""
    found = (state.get("mods") or []) + (state.get("packs") or [])
    return [
        f"{item['title']} ({item.get('version') or '?'} → {item['update']})"
        for item in found[:MAX_NAMES]
    ]


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def remember(root_dir, server_id, kind: str, items, **choices) -> None:
    """Keep what the Mods tab (or a check) found: kind is "mods" or
    "packs". choices: platform and game_version chosen on the Mods tab
    (None clears a choice), left as they are when not given."""
    state = get(root_dir, server_id)
    state[kind] = outdated(items)
    state[f"{kind}_checked"] = _now()
    for key in ("platform", "game_version"):
        if key in choices:
            state[key] = choices[key]
    _save(root_dir, server_id, state)


def target(server_data: dict, stats_version: str, state: dict):
    """The platform and Minecraft version to check with: what Crafty finds,
    else what was chosen on the Mods tab. A choice wins over what is found
    (it was made because the found one was wrong)."""
    platform = state.get("platform") or modrinth.detect_platform(
        server_data["path"], server_data["executable"], server_data["execution_command"]
    )
    if platform not in modrinth.PLATFORMS:
        platform = None
    game_version = state.get("game_version") or modrinth.detect_game_version(
        server_data["path"],
        stats_version,
        server_data["executable"],
        server_data["execution_command"],
    )
    return platform, game_version


def check(root_dir, server_data: dict, stats_version: str) -> dict:
    """Ask Modrinth about this server's files now and keep the result."""
    server_id = server_data["server_id"]
    state = get(root_dir, server_id)
    platform, game_version = target(server_data, stats_version, state)
    path = server_data["path"]
    if platform:
        try:
            jars = modrinth.installed(path, platform, game_version)
            remember(root_dir, server_id, "mods", jars)
        except modrinth.ModrinthError as ex:
            logger.info(f"Mod update check for {server_id}: {ex}")
    if platform not in modrinth.PROXIES and game_version:
        try:
            packs = datapacks.installed(path, game_version)
            remember(root_dir, server_id, "packs", packs)
        except modrinth.ModrinthError as ex:
            logger.info(f"Data pack update check for {server_id}: {ex}")
    return get(root_dir, server_id)


def check_all(controller, root_dir) -> None:
    """Check every Minecraft Java server (the scheduled job)."""
    for server in controller.servers.get_all_defined_servers():
        if server.get("type") != "minecraft-java":
            continue
        try:
            stats = controller.servers.get_server_stats_by_id(server["server_id"])
            check(root_dir, server, str(stats.get("version") or ""))
        except Exception as ex:  # pylint: disable=broad-exception-caught
            # One server's trouble must not stop the others
            logger.warning(f"Mod update check for {server.get('server_id')}: {ex}")
        time.sleep(PAUSE_SECONDS)


def update_all(root_dir, server_data: dict, stats_version: str) -> dict:
    """Install every update found now (the scheduled task; the server is
    stopped and backed up first). Returns {"updated": [files], "failed":
    ["name: why"]}."""
    server_id = str(server_data["server_id"])
    state = check(root_dir, server_data, stats_version)
    platform, game_version = target(server_data, stats_version, state)
    path = server_data["path"]
    updated, failed = [], []
    jobs = []
    if platform:
        jobs += [("mods", item) for item in state.get("mods") or []]
    if platform not in modrinth.PROXIES and game_version:
        jobs += [("packs", item) for item in state.get("packs") or []]
    for kind, item in jobs:
        try:
            if kind == "mods":
                result = modrinth.install(
                    path, platform, game_version, item["project_id"], server_id
                )
            else:
                result = datapacks.install(
                    path, game_version, item["project_id"], server_id
                )
            updated += [
                done["file"] for done in result["installed"] if not done["up_to_date"]
            ]
        except (modrinth.ModrinthError, OSError) as ex:
            failed.append(f"{item['title']}: {ex}")
    check(root_dir, server_data, stats_version)
    return {"updated": updated, "failed": failed}
