import json
import logging

import tornado.ioloop

from app.classes.helpers import modrinth
from app.classes.models.server_permissions import EnumPermissionsServer
from app.classes.web.base_api_handler import BaseApiHandler
from app.classes.web.routes.api.refused import Refused

logger = logging.getLogger(__name__)

MODRINTH_ERROR_STATUS = {
    "INVALID_PROJECT": 400,
    "NOT_FOUND": 404,
    "NO_COMPATIBLE_VERSION": 404,
    "BUSY": 409,
    "FILE_TOO_BIG": 413,
}


def _authorize_mods(handler: BaseApiHandler, server_id: str):
    """The auth data if the user may install mods and plugins on this server
    (the Files permission: uploading a jar does the same).

    Otherwise the error response has been sent and None is returned.
    """
    auth_data = handler.authenticate_user()
    if not auth_data:
        return None
    not_authorized = {
        "status": "error",
        "error": "NOT_AUTHORIZED",
        "error_data": handler.helper.translation.translate(
            "validators", "insufficientPerms", auth_data[4]["lang"]
        ),
    }
    if server_id not in [str(x["server_id"]) for x in auth_data[0]]:
        handler.finish_json(400, not_authorized)
        return None
    mask = handler.controller.server_perms.get_lowest_api_perm_mask(
        handler.controller.server_perms.get_user_permissions_mask(
            auth_data[4]["user_id"], server_id
        ),
        auth_data[5],
    )
    if EnumPermissionsServer.FILES not in (
        handler.controller.server_perms.get_permissions(mask)
    ):
        handler.finish_json(400, not_authorized)
        return None
    return auth_data


def _target(handler: BaseApiHandler, server_id: str, chosen: dict):
    """The server's data, platform and Minecraft version. The page can
    choose them (chosen["platform"], chosen["game_version"]) when they were
    not found or were found wrong."""
    server_data = handler.controller.servers.get_server_data_by_id(server_id)
    if server_data["type"] != "minecraft-java":
        raise Refused(400, "NOT_SUPPORTED", "Modrinth is for Minecraft Java servers")
    platform = chosen.get("platform") or modrinth.detect_platform(
        server_data["path"],
        server_data["executable"],
        server_data["execution_command"],
    )
    if platform is not None and platform not in modrinth.PLATFORMS:
        raise Refused(400, "INVALID_PLATFORM", "Unknown server platform")
    game_version = chosen.get("game_version")
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
    return server_data, platform, game_version


def _refused(ex: modrinth.ModrinthError) -> Refused:
    return Refused(MODRINTH_ERROR_STATUS.get(ex.code, 502), ex.code, str(ex))


async def _run(function, *args):
    return await tornado.ioloop.IOLoop.current().run_in_executor(None, function, *args)


class ApiServersServerModrinthHandler(BaseApiHandler):
    """What the Mods page shows: the server's platform and version, and the
    plugins or mods it has."""

    async def get(self, server_id: str):
        if not _authorize_mods(self, server_id):
            return
        chosen = {
            "platform": self.get_query_argument("platform", None),
            "game_version": self.get_query_argument("game_version", None),
        }
        try:
            server_data, platform, game_version = _target(self, server_id, chosen)
            info = modrinth.platform_info(platform, game_version)
            info["platforms"] = modrinth.PLATFORM_NAMES
            info["installed"] = []
            if info["supported"]:
                info["installed"] = await _run(
                    modrinth.installed, server_data["path"], platform, game_version
                )
        except modrinth.ModrinthError as ex:
            _refused(ex).send(self)
            return
        except Refused as ex:
            ex.send(self)
            return
        self.finish_json(200, {"status": "ok", "data": info})


class ApiServersServerModrinthSearchHandler(BaseApiHandler):
    """One page of Modrinth projects this server can load."""

    async def get(self, server_id: str):
        if not _authorize_mods(self, server_id):
            return
        chosen = {
            "platform": self.get_query_argument("platform", None),
            "game_version": self.get_query_argument("game_version", None),
        }
        try:
            _, platform, game_version = _target(self, server_id, chosen)
            if platform is None:
                raise Refused(400, "NOT_SUPPORTED", "Choose the server's platform")
            try:
                offset = int(self.get_query_argument("offset", "0"))
            except ValueError as ex:
                raise Refused(400, "INVALID_OFFSET", "offset: a number") from ex
            data = await _run(
                modrinth.search,
                platform,
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


class ApiServersServerModrinthInstallHandler(BaseApiHandler):
    """Install (or update) a project and what it needs into the plugins or
    mods folder. The server loads it on its next start."""

    async def post(self, server_id: str):
        auth_data = _authorize_mods(self, server_id)
        if not auth_data:
            return
        try:
            body = json.loads(self.request.body)
            if not isinstance(body, dict):
                raise Refused(400, "INVALID_JSON", "Send a JSON object")
            server_data, platform, game_version = _target(
                self,
                server_id,
                {
                    "platform": body.get("platform"),
                    "game_version": body.get("game_version"),
                },
            )
            if platform is None:
                raise Refused(400, "NOT_SUPPORTED", "Choose the server's platform")
            project_id = str(body.get("project_id") or "")
            result = await _run(
                modrinth.install,
                server_data["path"],
                platform,
                game_version,
                project_id,
                server_id,
            )
        except json.decoder.JSONDecodeError as ex:
            Refused(400, "INVALID_JSON", str(ex)).send(self)
            return
        except modrinth.ModrinthError as ex:
            _refused(ex).send(self)
            return
        except Refused as ex:
            ex.send(self)
            return
        except OSError as ex:
            logger.exception(f"Could not install {body.get('project_id')}")
            Refused(500, "INSTALL_FAILED", str(ex)).send(self)
            return

        names = ", ".join(item["file"] for item in result["installed"])
        self.controller.management.add_to_audit_log(
            auth_data[4]["user_id"],
            f"installed {names} from Modrinth on server {server_data['server_name']}",
            server_id,
            self.get_remote_ip(),
        )
        svr = self.controller.servers.get_server_instance_by_id(server_id)
        result["restart_needed"] = bool(svr.check_running())
        self.finish_json(200, {"status": "ok", "data": result})
