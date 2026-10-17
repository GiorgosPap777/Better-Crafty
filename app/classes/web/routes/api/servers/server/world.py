import json
import logging
import shutil
import threading
import uuid
from pathlib import Path

import tornado.ioloop

from app.classes.helpers import world_tools
from app.classes.models.server_permissions import EnumPermissionsServer
from app.classes.web.base_api_handler import BaseApiHandler

logger = logging.getLogger(__name__)

DIMENSION_NAMES = {world_tools.NETHER: "Nether", world_tools.END: "End"}
WORLD_ERROR_STATUS = {
    "INVALID_DIMENSION": 400,
    "WORLD_NOT_FOUND": 404,
    "NOTHING_TO_RESET": 409,
}
# Room for the zip's own records on top of the world's size
ZIP_SPARE_SPACE = 64 * 1024 * 1024


class Refused(Exception):
    """An error answer: the HTTP status, the error name and a message."""

    def __init__(self, status: int, error: str, message: str):
        super().__init__(message)
        self.status = status
        self.error = error

    def send(self, handler: BaseApiHandler) -> None:
        handler.finish_json(
            self.status,
            {"status": "error", "error": self.error, "error_data": str(self)},
        )


def _authorize_world(handler: BaseApiHandler, server_id: str):
    """The auth data if the user may use this server's world tools (the
    Backup permission: backups can replace the whole world anyway).

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
    if EnumPermissionsServer.BACKUP not in (
        handler.controller.server_perms.get_permissions(mask)
    ):
        handler.finish_json(400, not_authorized)
        return None
    return auth_data


def _make_zip(svr, server_path, roots, target: Path, running: bool):
    """Zip the world; a running Java server saves everything first and does
    not save again until the zip is done. Returns (files, saved)."""
    saved = None
    if running:
        saved = svr.flush_and_hold_saves()
    try:
        return world_tools.zip_world(server_path, roots, target), saved
    finally:
        if running and svr.check_running():
            svr.send_command("save-on")


def _zip_in_background(svr, server_data, roots, target: Path, running, user_id):
    server_id = str(server_data["server_id"])
    try:
        files, saved = _make_zip(svr, server_data["path"], roots, target, running)
        world_tools.downloads.finish(server_id, user_id, target, files, saved)
    except Exception as ex:
        logger.exception(f"Could not zip the world of {server_id}")
        world_tools.downloads.fail(server_id, user_id, "ZIP_FAILED", str(ex))
    finally:
        world_tools.end(server_id)


class ApiServersServerWorldHandler(BaseApiHandler):
    """What the World page shows: the world, its size and its dimensions."""

    async def get(self, server_id: str):
        auth_data = _authorize_world(self, server_id)
        if not auth_data:
            return
        server_data = self.controller.servers.get_server_data_by_id(server_id)
        svr = self.controller.servers.get_server_instance_by_id(server_id)
        info = await tornado.ioloop.IOLoop.current().run_in_executor(
            None, world_tools.overview, server_data["path"], server_data["type"]
        )
        if info is None:
            Refused(400, "NOT_SUPPORTED", "World tools are for Minecraft servers").send(
                self
            )
            return
        info["running"] = bool(svr.check_running())
        info["busy"] = world_tools.busy(server_id)
        info["download"] = world_tools.downloads.status(
            server_id, auth_data[4]["user_id"]
        )
        self.finish_json(200, {"status": "ok", "data": info})


class ApiServersServerWorldDownloadHandler(BaseApiHandler):
    """POST starts making a zip of the world and GET tells how it is going;
    GET with the zip's token sends it, once."""

    async def post(self, server_id: str):
        auth_data = _authorize_world(self, server_id)
        if not auth_data:
            return
        user_id = auth_data[4]["user_id"]
        try:
            await self._start(server_id, user_id)
        except Refused as ex:
            ex.send(self)
            return
        self.finish_json(
            200,
            {"status": "ok", "data": world_tools.downloads.status(server_id, user_id)},
        )

    async def _start(self, server_id: str, user_id) -> None:
        server_data = self.controller.servers.get_server_data_by_id(server_id)
        svr = self.controller.servers.get_server_instance_by_id(server_id)
        roots = world_tools.world_roots(server_data["path"], server_data["type"])
        if not roots:
            raise Refused(404, "WORLD_NOT_FOUND", "This server has no world")
        running = bool(svr.check_running())
        if running and server_data["type"] == "minecraft-bedrock":
            raise Refused(
                409, "STOP_SERVER_FIRST", "Stop the server to download a Bedrock world"
            )
        other = world_tools.begin(server_id, "download")
        if other:
            raise Refused(409, "WORLD_BUSY", f"Busy with a world {other}")

        folder = Path(
            self.controller.project_root, "temp", "world-downloads", uuid.uuid4().hex
        )
        started = False
        try:
            world_tools.downloads.purge()
            size = await tornado.ioloop.IOLoop.current().run_in_executor(
                None, lambda: sum(world_tools.folder_size(root) for root in roots)
            )
            folder.mkdir(parents=True)
            if not self.file_helper.has_enough_storage(
                size + ZIP_SPARE_SPACE, self.file_helper.get_drive_free_space(folder)
            ):
                raise Refused(
                    507,
                    "OUT_OF_SPACE",
                    "There is not enough free disk space for the zip",
                )
            target = folder / world_tools.download_name(
                server_data["server_name"], roots[0].name
            )
            world_tools.downloads.start(server_id, user_id, folder)
            threading.Thread(
                target=_zip_in_background,
                args=(svr, server_data, roots, target, running, user_id),
                name=f"world_zip_{server_id}",
                daemon=True,
            ).start()
            started = True
        except OSError as ex:
            logger.exception(f"Could not start zipping the world of {server_id}")
            raise Refused(500, "ZIP_FAILED", str(ex)) from ex
        finally:
            if not started:
                shutil.rmtree(folder, ignore_errors=True)
                world_tools.end(server_id)

    async def get(self, server_id: str, token: str = None):
        auth_data = _authorize_world(self, server_id)
        if not auth_data:
            return
        user_id = auth_data[4]["user_id"]
        if token is None:
            self.finish_json(
                200,
                {
                    "status": "ok",
                    "data": world_tools.downloads.status(server_id, user_id),
                },
            )
            return
        path = world_tools.downloads.take(token, user_id, server_id)
        if path is None or not path.is_file():
            Refused(
                404,
                "DOWNLOAD_NOT_FOUND",
                "This download was already fetched or has expired",
            ).send(self)
            return
        server_data = self.controller.servers.get_server_data_by_id(server_id)
        self.controller.management.add_to_audit_log(
            user_id,
            f"downloaded the world of server {server_data['server_name']}",
            server_id,
            self.get_remote_ip(),
        )
        try:
            self.set_header("Content-Length", path.stat().st_size)
            await self.download_file(path)
        finally:
            shutil.rmtree(path.parent, ignore_errors=True)


class ApiServersServerWorldResetHandler(BaseApiHandler):
    """Delete the Nether or the End of a stopped Java server."""

    async def post(self, server_id: str):
        auth_data = _authorize_world(self, server_id)
        if not auth_data:
            return
        try:
            dimension = self._dimension()
            server_data = self._check_server(server_id)
            other = world_tools.begin(server_id, "reset")
            if other:
                raise Refused(409, "WORLD_BUSY", f"Busy with a world {other}")
            try:
                result = await tornado.ioloop.IOLoop.current().run_in_executor(
                    None, world_tools.reset_dimension, server_data["path"], dimension
                )
            except world_tools.WorldError as ex:
                raise Refused(
                    WORLD_ERROR_STATUS.get(ex.code, 500), ex.code, str(ex)
                ) from ex
            except OSError as ex:
                logger.exception(f"Could not reset the {dimension} of {server_id}")
                raise Refused(500, "RESET_FAILED", str(ex)) from ex
            finally:
                world_tools.end(server_id)
        except Refused as ex:
            ex.send(self)
            return

        self.controller.management.add_to_audit_log(
            auth_data[4]["user_id"],
            f"reset the {DIMENSION_NAMES[dimension]} of server "
            f"{server_data['server_name']}",
            server_id,
            self.get_remote_ip(),
        )
        self.finish_json(200, {"status": "ok", "data": result})

    def _dimension(self) -> str:
        try:
            data = json.loads(self.request.body)
        except json.decoder.JSONDecodeError as ex:
            raise Refused(400, "INVALID_JSON", str(ex)) from ex
        dimension = data.get("dimension") if isinstance(data, dict) else None
        if dimension not in world_tools.RESETTABLE:
            raise Refused(400, "INVALID_DIMENSION", "dimension: the_nether or the_end")
        return dimension

    def _check_server(self, server_id: str) -> dict:
        server_data = self.controller.servers.get_server_data_by_id(server_id)
        if server_data["type"] != "minecraft-java":
            raise Refused(
                400, "NOT_SUPPORTED", "Only Java worlds keep dimensions apart"
            )
        svr = self.controller.servers.get_server_instance_by_id(server_id)
        if svr.check_running() or svr.updating:
            raise Refused(409, "SERVER_RUNNING", "Stop the server first")
        if svr.is_backingup:
            raise Refused(409, "BACKUP_RUNNING", "Wait until the backup has finished")
        return server_data
