# TODO: create and read

import json
import logging

from croniter import croniter
from peewee import DoesNotExist
from playhouse.shortcuts import model_to_dict
from jsonschema import ValidationError, validate
from app.classes.models.server_permissions import EnumPermissionsServer
from app.classes.shared.restart_countdown import CHOICES, parse_minutes
from app.classes.web.base_api_handler import BaseApiHandler

logger = logging.getLogger(__name__)


def action_id_error(controller, server_id: str, action, action_id) -> dict | None:
    """Why a schedule's action_id does not fit its action, or None.

    A restart keeps the minutes to warn the players first; a backup keeps the
    id of one of this server's backup configs."""
    if not action_id:
        return None
    if action == "restart":
        if parse_minutes(action_id) is None:
            return {
                "status": "error",
                "error": "INVALID_WARNING_TIME",
                "error_data": "The warning time must be one of "
                + ", ".join(str(choice) for choice in CHOICES)
                + " minutes.",
            }
        return None
    try:
        backup_config = controller.management.get_backup_config(action_id)
    except DoesNotExist:
        return {"status": "error", "error": "BACKUP_NOT_FOUND"}
    if backup_config["server_id"]["server_id"] != server_id:
        return {"status": "error", "error": "Server ID Mismatch"}
    return None


new_task_schema = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "error": "typeString",
            "fill": True,
        },
        "enabled": {
            "type": "boolean",
            "default": True,
            "error": "typeBool",
            "fill": True,
        },
        "action": {
            "type": "string",
            "error": "typeString",
            "fill": True,
        },
        "action_id": {
            "type": "string",
            "error": "typeString",
            "fill": True,
        },
        "interval": {
            "type": "integer",
            "error": "typeInteger",
            "fill": True,
        },
        "interval_type": {
            "type": "string",
            "enum": [
                # Basic tasks
                "hours",
                "minutes",
                "days",
                # Chain reaction tasks:
                "reaction",
                # CRON tasks:
                "",
            ],
            "error": "enumErr",
            "fill": True,
        },
        "start_time": {
            "type": "string",
            "pattern": r"\d{1,2}:\d{1,2}",
            "error": "typeString",
            "fill": True,
        },
        "command": {
            "type": ["string", "null"],
            "error": "typeString",
            "fill": True,
        },
        "one_time": {
            "type": "boolean",
            "default": False,
            "error": "typeBool",
            "fill": True,
        },
        "cron_string": {
            "type": "string",
            "default": "",
            "error": "typeString",
            "fill": True,
        },
        "parent": {
            "type": ["integer", "null"],
            "error": "typeInteger",
            "fill": True,
        },
        "delay": {
            "type": "integer",
            "default": 0,
            "error": "typeInteger",
            "fill": True,
        },
    },
    "additionalProperties": False,
    "minProperties": 1,
}


class ApiServersServerTasksIndexHandler(BaseApiHandler):
    def get(self, server_id: str):
        auth_data = self.authenticate_user()
        if not auth_data:
            return
        if server_id not in [str(x["server_id"]) for x in auth_data[0]]:
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
        mask = self.controller.server_perms.get_lowest_api_perm_mask(
            self.controller.server_perms.get_user_permissions_mask(
                auth_data[4]["user_id"], server_id
            ),
            auth_data[5],
        )
        server_permissions = self.controller.server_perms.get_permissions(mask)
        if EnumPermissionsServer.SCHEDULE not in server_permissions:
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
        schedules = [
            model_to_dict(schedule, recurse=False)
            for schedule in self.controller.management.get_schedules_by_server(
                server_id
            )
        ]
        self.finish_json(200, {"status": "ok", "data": schedules})

    def post(self, server_id: str):
        auth_data = self.authenticate_user()
        if not auth_data:
            return

        try:
            data = json.loads(self.request.body)
        except json.decoder.JSONDecodeError as e:
            return self.finish_json(
                400, {"status": "error", "error": "INVALID_JSON", "error_data": str(e)}
            )

        try:
            validate(data, new_task_schema)
        except ValidationError as why:
            offending_key = ""
            if why.schema.get("fill", None):
                offending_key = why.path[0] if why.path else None
            err = f"""{offending_key} {self.translator.translate(
                "validators",
                why.schema.get("error", "additionalProperties"),
                self.controller.users.get_user_lang_by_id(auth_data[4]["user_id"]),
            )} {why.schema.get("enum", "")}"""
            return self.finish_json(
                400,
                {
                    "status": "error",
                    "error": "INVALID_JSON_SCHEMA",
                    "error_data": f"{str(err)}",
                },
            )

        if server_id not in [str(x["server_id"]) for x in auth_data[0]]:
            # if the user doesn't have access to the server, return an error
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
        mask = self.controller.server_perms.get_lowest_api_perm_mask(
            self.controller.server_perms.get_user_permissions_mask(
                auth_data[4]["user_id"], server_id
            ),
            auth_data[5],
        )
        server_permissions = self.controller.server_perms.get_permissions(mask)
        if EnumPermissionsServer.SCHEDULE not in server_permissions:
            # if the user doesn't have Schedule permission, return an error
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
        data["server_id"] = server_id
        if not data.get("start_time"):
            data["start_time"] = "00:00"
        # Fill in optional fields so a minimal request does not fail later
        data.setdefault("enabled", True)
        data.setdefault("command", None)
        data.setdefault("one_time", False)
        data.setdefault("cron_string", "")
        data.setdefault("delay", 0)
        for key in ("name", "action", "interval", "interval_type"):
            if key not in data:
                return self.finish_json(
                    400,
                    {
                        "status": "error",
                        "error": "INVALID_JSON_SCHEMA",
                        "error_data": f"{key} is required",
                    },
                )

        # validate cron string
        if "cron_string" in data:
            if data["cron_string"] != "" and not croniter.is_valid(data["cron_string"]):
                return self.finish_json(
                    405,
                    {
                        "status": "error",
                        "error": self.helper.translation.translate(
                            "error",
                            "cronFormat",
                            self.controller.users.get_user_lang_by_id(
                                auth_data[4]["user_id"]
                            ),
                        ),
                    },
                )
        if "parent" not in data:
            data["parent"] = None
        error = action_id_error(
            self.controller, server_id, data["action"], data.get("action_id")
        )
        if error:
            return self.finish_json(405, error)
        task_id = self.tasks_manager.schedule_job(data)

        self.controller.management.add_to_audit_log(
            auth_data[4]["user_id"],
            f"Edited server {server_id}: added schedule",
            server_id,
            self.get_remote_ip(),
        )
        self.tasks_manager.reload_schedule_from_db()

        self.finish_json(200, {"status": "ok", "data": {"schedule_id": task_id}})
