import logging
from pathlib import Path

import tornado.ioloop

from app.classes.helpers import modpacks, modrinth
from app.classes.helpers.helpers import Helpers
from app.classes.web.base_api_handler import BaseApiHandler
from app.classes.web.routes.api.refused import Refused

logger = logging.getLogger(__name__)

ERROR_STATUS = {
    "INVALID_PROJECT": 400,
    "NOT_FOUND": 404,
    "NOT_A_MODPACK": 400,
    "BAD_PACK": 400,
    "UNSUPPORTED_LOADER": 400,
    "PACK_TOO_BIG": 413,
}


def _authorize(handler: BaseApiHandler) -> bool:
    """Whether the user may make servers; otherwise the error is sent."""
    auth_data = handler.authenticate_user()
    if not auth_data:
        return False
    user = auth_data[4]
    if user["superuser"] or handler.controller.crafty_perms.can_create_server(
        user["user_id"]
    ):
        return True
    handler.finish_json(
        400,
        {
            "status": "error",
            "error": "NOT_AUTHORIZED",
            "error_data": handler.helper.translation.translate(
                "validators", "insufficientPerms", user["lang"]
            ),
        },
    )
    return False


async def _answer(handler: BaseApiHandler, function, *args):
    try:
        data = await tornado.ioloop.IOLoop.current().run_in_executor(
            None, function, *args
        )
    except modrinth.ModrinthError as ex:
        Refused(ERROR_STATUS.get(ex.code, 502), ex.code, str(ex)).send(handler)
        return
    handler.finish_json(200, {"status": "ok", "data": data})


class ApiCraftyModpacksHandler(BaseApiHandler):
    """One page of Modrinth modpacks that can run on a server."""

    async def get(self):
        if not _authorize(self):
            return
        try:
            offset = int(self.get_query_argument("offset", "0"))
        except ValueError:
            Refused(400, "INVALID_OFFSET", "offset: a number").send(self)
            return
        await _answer(
            self,
            modrinth.search_modpacks,
            self.get_query_argument("query", ""),
            offset,
        )


class ApiCraftyModpackVersionsHandler(BaseApiHandler):
    """A modpack's versions, newest first."""

    async def get(self):
        if not _authorize(self):
            return
        await _answer(
            self, modrinth.modpack_versions, self.get_query_argument("project_id", "")
        )


class ApiCraftyModpackFileHandler(BaseApiHandler):
    """What is in an uploaded .mrpack (name is its file name in the import
    folder)."""

    async def get(self):
        if not _authorize(self):
            return
        name = self.get_query_argument("name", "")
        folder = Path(self.controller.project_root, "import", "upload")
        try:
            if not name.lower().endswith(".mrpack"):
                raise ValueError("Not a .mrpack file")
            path = Helpers.validate_traversal(folder, name)
        except ValueError as ex:
            Refused(400, "INVALID_NAME", str(ex)).send(self)
            return
        if not path.is_file():
            Refused(404, "NOT_FOUND", "The file is not there").send(self)
            return
        await _answer(self, modpacks.summary, path)
