import logging

from app.classes.models.server_permissions import EnumPermissionsServer
from app.classes.web.base_api_handler import BaseApiHandler

logger = logging.getLogger(__name__)


class ApiServersServerPlayersHandler(BaseApiHandler):
    """Known players, bans, whitelist and operators of a server."""

    def get(self, server_id: str):
        auth_data = self.authenticate_user()
        if not auth_data:
            return
        not_authorized = {
            "status": "error",
            "error": "NOT_AUTHORIZED",
            "error_data": self.helper.translation.translate(
                "validators", "insufficientPerms", auth_data[4]["lang"]
            ),
        }
        if server_id not in [str(x["server_id"]) for x in auth_data[0]]:
            return self.finish_json(400, not_authorized)
        mask = self.controller.server_perms.get_lowest_api_perm_mask(
            self.controller.server_perms.get_user_permissions_mask(
                auth_data[4]["user_id"], server_id
            ),
            auth_data[5],
        )
        if EnumPermissionsServer.PLAYERS not in (
            self.controller.server_perms.get_permissions(mask)
        ):
            return self.finish_json(400, not_authorized)

        self.finish_json(
            200,
            {
                "status": "ok",
                "data": self.controller.servers.get_player_overview(server_id),
            },
        )
