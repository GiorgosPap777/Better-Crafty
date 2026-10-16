import logging
from app.classes.helpers.item_icons import ItemIcons
from app.classes.web.base_api_handler import BaseApiHandler

logger = logging.getLogger(__name__)


class ApiCraftyItemIconsHandler(BaseApiHandler):
    """Whether item pictures are there (GET), and making them (POST)."""

    def get(self):
        auth_data = self.authenticate_user()
        if not auth_data:
            return
        self.finish_json(
            200,
            {"status": "ok", "data": ItemIcons.get(self.helper.config_dir).status()},
        )

    def post(self):
        auth_data = self.authenticate_user()
        if not auth_data:
            return
        if not auth_data[3]:
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "NOT_AUTHORIZED",
                    "error_data": self.helper.translation.translate(
                        "validators", "insufficientPerms", auth_data[4]["lang"]
                    ),
                },
            )
        icons = ItemIcons.get(self.helper.config_dir)
        if icons.start():
            self.controller.management.add_to_audit_log(
                auth_data[4]["user_id"],
                "Started downloading Minecraft item pictures from Mojang",
                None,
                self.get_remote_ip(),
            )
        self.finish_json(200, {"status": "ok", "data": icons.status()})


class ApiCraftyItemIconHandler(BaseApiHandler):
    """One item picture, for signed-in users only (the art is Mojang's)."""

    def get(self, name: str):
        auth_data = self.authenticate_user()
        if not auth_data:
            return
        path = ItemIcons.get(self.helper.config_dir).path(name)
        if path is None:
            self.set_status(404)
            return self.finish()
        self.set_header("Content-Type", "image/png")
        self.set_header("Cache-Control", "private, max-age=604800")
        self.finish(path.read_bytes())
