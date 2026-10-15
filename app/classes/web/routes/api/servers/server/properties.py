import json
import logging
from pathlib import Path

from app.classes.helpers import server_properties
from app.classes.models.server_permissions import EnumPermissionsServer
from app.classes.web.base_api_handler import BaseApiHandler

logger = logging.getLogger(__name__)


class ApiServersServerPropertiesHandler(BaseApiHandler):
    """Friendly access to the common settings in server.properties."""

    def _prepare(self, server_id: str):
        """Check access and find the file. Returns (auth_data, path, type) or None."""
        auth_data = self.authenticate_user()
        if not auth_data:
            return None
        lang = auth_data[4]["lang"]
        not_authorized = {
            "status": "error",
            "error": "NOT_AUTHORIZED",
            "error_data": self.helper.translation.translate(
                "validators", "insufficientPerms", lang
            ),
        }
        if server_id not in [str(x["server_id"]) for x in auth_data[0]]:
            self.finish_json(400, not_authorized)
            return None
        mask = self.controller.server_perms.get_lowest_api_perm_mask(
            self.controller.server_perms.get_user_permissions_mask(
                auth_data[4]["user_id"], server_id
            ),
            auth_data[5],
        )
        if EnumPermissionsServer.CONFIG not in (
            self.controller.server_perms.get_permissions(mask)
        ):
            self.finish_json(400, not_authorized)
            return None

        server_type = self.controller.servers.get_server_type_by_id(server_id)
        server_data = self.controller.servers.get_server_data_by_id(server_id)
        path = Path(server_data["path"], "server.properties")
        if server_properties.fields_for(server_type) is None or not path.is_file():
            self.finish_json(
                404,
                {
                    "status": "error",
                    "error": "NO_SERVER_PROPERTIES",
                    "error_data": "This server has no server.properties file.",
                },
            )
            return None
        return auth_data, path, server_type

    def _settings_for_page(self, path, server_type, lang):
        settings = server_properties.read_settings(path, server_type)
        for setting in settings:
            setting["label"] = self.helper.translation.translate(
                "serverProperties", setting["key"], lang, error=False
            )
        return settings

    def get(self, server_id: str):
        prepared = self._prepare(server_id)
        if prepared is None:
            return
        auth_data, path, server_type = prepared
        try:
            settings = self._settings_for_page(path, server_type, auth_data[4]["lang"])
        except OSError as why:
            logger.error(f"Could not read {path}: {why}")
            return self.finish_json(
                500,
                {"status": "error", "error": "READ_FAILED", "error_data": str(why)},
            )
        self.finish_json(200, {"status": "ok", "data": settings})

    def patch(self, server_id: str):
        prepared = self._prepare(server_id)
        if prepared is None:
            return
        auth_data, path, server_type = prepared
        try:
            data = json.loads(self.request.body)
        except json.decoder.JSONDecodeError as why:
            return self.finish_json(
                400,
                {"status": "error", "error": "INVALID_JSON", "error_data": str(why)},
            )
        if not isinstance(data, dict) or not data:
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "INVALID_JSON",
                    "error_data": "Send an object of settings to change.",
                },
            )
        try:
            changes = server_properties.validate_changes(data, server_type)
            present = {
                s["key"] for s in server_properties.read_settings(path, server_type)
            }
            missing = [key for key in changes if key not in present]
            if missing:
                raise ValueError(f"{missing[0]} is not in server.properties")
            server_properties.write_changes(path, changes)
        except ValueError as why:
            return self.finish_json(
                400,
                {"status": "error", "error": "INVALID_SETTING", "error_data": str(why)},
            )
        except OSError as why:
            logger.error(f"Could not write {path}: {why}")
            return self.finish_json(
                500,
                {"status": "error", "error": "WRITE_FAILED", "error_data": str(why)},
            )

        self.controller.management.add_to_audit_log(
            auth_data[4]["user_id"],
            f"Edited server {server_id}: changed server.properties "
            f"({', '.join(sorted(changes))})",
            server_id,
            self.get_remote_ip(),
        )
        self.finish_json(200, {"status": "ok"})
