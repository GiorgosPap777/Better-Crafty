import json
import logging

from app.classes.helpers import datapacks, mod_updates, modrinth
from app.classes.web.base_api_handler import BaseApiHandler
from app.classes.web.routes.api.refused import Refused
from app.classes.web.routes.api.servers.server.modrinth import (
    _authorize_mods,
    _refused,
    _run,
)

logger = logging.getLogger(__name__)


def _target(handler: BaseApiHandler, server_id: str, game_version=None):
    """The server's data and Minecraft version (the page can give the
    version when it was not found)."""
    server_data = handler.controller.servers.get_server_data_by_id(server_id)
    if server_data["type"] != "minecraft-java":
        raise Refused(400, "NOT_SUPPORTED", "Data packs are for Minecraft Java servers")
    platform = modrinth.detect_platform(
        server_data["path"], server_data["executable"], server_data["execution_command"]
    )
    if platform in modrinth.PROXIES:
        raise Refused(400, "NOT_SUPPORTED", "A proxy has no world for data packs")
    if game_version:
        if not modrinth.GAME_VERSION.match(game_version):
            raise Refused(400, "INVALID_VERSION", "Not a Minecraft version")
    else:
        stats = handler.controller.servers.get_server_stats_by_id(server_id)
        game_version = modrinth.detect_game_version(
            server_data["path"],
            str(stats.get("version") or ""),
            server_data["executable"],
            server_data["execution_command"],
        )
    return server_data, game_version


def _body(handler: BaseApiHandler) -> dict:
    try:
        body = json.loads(handler.request.body)
    except json.decoder.JSONDecodeError as ex:
        raise Refused(400, "INVALID_JSON", str(ex)) from ex
    if not isinstance(body, dict):
        raise Refused(400, "INVALID_JSON", "Send a JSON object")
    return body


def _running(handler: BaseApiHandler, server_id: str) -> bool:
    svr = handler.controller.servers.get_server_instance_by_id(server_id)
    return bool(svr.check_running())


class ApiServersServerDatapacksHandler(BaseApiHandler):
    """What the Data packs page shows: the world's datapacks folder, the
    Minecraft version and the packs in the folder."""

    async def get(self, server_id: str):
        if not _authorize_mods(self, server_id):
            return
        chosen_version = self.get_query_argument("game_version", None)
        try:
            server_data, game_version = _target(self, server_id, chosen_version)
            path = server_data["path"]
            world = datapacks.world_folder(path)
            info = {
                "supported": True,
                "folder": f"{world.name}/{datapacks.FOLDER}",
                "world_exists": world.is_dir(),
                "game_version": game_version,
                "running": _running(self, server_id),
                "modrinth_error": None,
            }
            try:
                info["installed"] = await _run(datapacks.installed, path, game_version)
                if game_version:
                    mod_updates.remember(
                        self.helper.root_dir,
                        server_id,
                        "packs",
                        info["installed"],
                        game_version=chosen_version,
                    )
                    info["update_count"] = mod_updates.count(
                        mod_updates.get(self.helper.root_dir, server_id)
                    )
            except modrinth.ModrinthError as ex:
                if ex.code == "BAD_FOLDER":
                    raise
                # Still show the packs, without their names from Modrinth
                info["modrinth_error"] = str(ex)
                info["installed"] = await _run(datapacks.local_packs, path)
        except modrinth.ModrinthError as ex:
            _refused(ex).send(self)
            return
        except Refused as ex:
            ex.send(self)
            return
        self.finish_json(200, {"status": "ok", "data": info})


class ApiServersServerDatapacksSearchHandler(BaseApiHandler):
    """One page of Modrinth data packs for this Minecraft version."""

    async def get(self, server_id: str):
        if not _authorize_mods(self, server_id):
            return
        try:
            _, game_version = _target(
                self, server_id, self.get_query_argument("game_version", None)
            )
            try:
                offset = int(self.get_query_argument("offset", "0"))
            except ValueError as ex:
                raise Refused(400, "INVALID_OFFSET", "offset: a number") from ex
            data = await _run(
                datapacks.search,
                game_version,
                self.get_query_argument("query", ""),
                offset,
            )
        except modrinth.ModrinthError as ex:
            _refused(ex).send(self)
            return
        except Refused as ex:
            ex.send(self)
            return
        self.finish_json(200, {"status": "ok", "data": data})


class ApiServersServerDatapacksVersionsHandler(BaseApiHandler):
    """The data pack versions of a project for this Minecraft version."""

    async def get(self, server_id: str):
        if not _authorize_mods(self, server_id):
            return
        try:
            _, game_version = _target(
                self, server_id, self.get_query_argument("game_version", None)
            )
            data = await _run(
                datapacks.versions,
                self.get_query_argument("project_id", ""),
                game_version,
            )
        except modrinth.ModrinthError as ex:
            _refused(ex).send(self)
            return
        except Refused as ex:
            ex.send(self)
            return
        self.finish_json(200, {"status": "ok", "data": data})


class ApiServersServerDatapacksInstallHandler(BaseApiHandler):
    """Install (or update) a data pack: {"project_id", "version_id"
    (optional, else the newest), "game_version" (optional)}."""

    async def post(self, server_id: str):
        auth_data = _authorize_mods(self, server_id)
        if not auth_data:
            return
        try:
            body = _body(self)
            server_data, game_version = _target(
                self, server_id, body.get("game_version")
            )
            version_id = body.get("version_id")
            result = await _run(
                datapacks.install,
                server_data["path"],
                game_version,
                str(body.get("project_id") or ""),
                server_id,
                str(version_id) if version_id else None,
            )
        except modrinth.ModrinthError as ex:
            _refused(ex).send(self)
            return
        except Refused as ex:
            ex.send(self)
            return
        except OSError as ex:
            logger.exception(
                f"Could not install the data pack {body.get('project_id')}"
            )
            Refused(500, "INSTALL_FAILED", str(ex)).send(self)
            return

        names = ", ".join(item["file"] for item in result["installed"])
        self.controller.management.add_to_audit_log(
            auth_data[4]["user_id"],
            f"installed the data pack {names} from Modrinth on server "
            f"{server_data['server_name']}",
            server_id,
            self.get_remote_ip(),
        )
        result["reload_needed"] = _running(self, server_id)
        self.finish_json(200, {"status": "ok", "data": result})


class ApiServersServerDatapacksPackHandler(BaseApiHandler):
    """Turn a data pack zip off or on, or remove a zip or a pack folder:
    {"file": "x.zip", "action": "disable" | "enable" | "remove"}."""

    async def post(self, server_id: str):
        auth_data = _authorize_mods(self, server_id)
        if not auth_data:
            return
        try:
            body = _body(self)
            server_data, _ = _target(self, server_id, None)
            name = str(body.get("file") or "")
            action = str(body.get("action") or "")
            new_name = await _run(
                datapacks.change_pack, server_data["path"], name, action
            )
        except modrinth.ModrinthError as ex:
            _refused(ex).send(self)
            return
        except Refused as ex:
            ex.send(self)
            return
        except OSError as ex:
            logger.exception(f"Could not change the data pack {body.get('file')}")
            Refused(500, "CHANGE_FAILED", str(ex)).send(self)
            return

        done = {"remove": "removed", "disable": "turned off", "enable": "turned on"}
        self.controller.management.add_to_audit_log(
            auth_data[4]["user_id"],
            f"{done[action]} the data pack {name} on server "
            f"{server_data['server_name']}",
            server_id,
            self.get_remote_ip(),
        )
        self.finish_json(
            200,
            {
                "status": "ok",
                "data": {
                    "file": new_name,
                    "reload_needed": _running(self, server_id),
                },
            },
        )
