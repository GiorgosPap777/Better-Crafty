import logging

import tornado.ioloop

from app.classes.helpers.player_skins import PlayerSkins
from app.classes.models.server_permissions import EnumPermissionsServer
from app.classes.web.base_api_handler import BaseApiHandler

logger = logging.getLogger(__name__)


def _authorize_players(handler: BaseApiHandler, server_id: str):
    """The auth data if the user may manage this server's players.

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
    if EnumPermissionsServer.PLAYERS not in (
        handler.controller.server_perms.get_permissions(mask)
    ):
        handler.finish_json(400, not_authorized)
        return None
    return auth_data


class ApiServersServerPlayersHandler(BaseApiHandler):
    """Known players, bans, whitelist and operators of a server."""

    def get(self, server_id: str):
        if not _authorize_players(self, server_id):
            return

        self.finish_json(
            200,
            {
                "status": "ok",
                "data": self.controller.servers.get_player_overview(server_id),
            },
        )


class ApiServersServerPlayerHandler(BaseApiHandler):
    """What a Java server has saved about one player (read-only)."""

    def get(self, server_id: str, uuid: str):
        if not _authorize_players(self, server_id):
            return

        try:
            details = self.controller.servers.get_player_details(server_id, uuid)
        except ValueError as ex:
            return self.finish_json(
                400,
                {"status": "error", "error": "INVALID_PLAYER", "error_data": str(ex)},
            )
        if details is None:
            return self.finish_json(
                404,
                {
                    "status": "error",
                    "error": "PLAYER_NOT_FOUND",
                    "error_data": "This server has no saved data for that player",
                },
            )
        self.finish_json(200, {"status": "ok", "data": details})


class ApiServersServerPlayerSkinHandler(BaseApiHandler):
    """A player's skin for the inventory picture (needs the item pictures)."""

    async def get(self, server_id: str, uuid: str):
        if not _authorize_players(self, server_id):
            return
        # Only players of this server, so Crafty never looks up anyone else
        if not self.controller.servers.has_player(server_id, uuid):
            self.set_status(404)
            return self.finish()
        found = await tornado.ioloop.IOLoop.current().run_in_executor(
            None, PlayerSkins.get(self.helper.config_dir).skin, uuid
        )
        if found is None:
            self.set_status(404)
            return self.finish()
        self.set_header("Content-Type", "image/png")
        self.set_header("X-Skin-Model", found[1])
        self.set_header("Cache-Control", "private, max-age=3600")
        self.finish(found[0])
