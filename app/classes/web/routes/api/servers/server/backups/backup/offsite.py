import json
import logging

import tornado.ioloop

from app.classes.helpers import offsite
from app.classes.models.offsite import HelperOffsite
from app.classes.models.server_permissions import EnumPermissionsServer
from app.classes.shared.offsite_copies import last_status
from app.classes.web.base_api_handler import BaseApiHandler
from app.classes.web.routes.api.refused import Refused

logger = logging.getLogger(__name__)

MAX_KEEP = 1000
FETCH_STATUS = {"ALREADY_HERE": 409, "OFFSITE_BUSY": 409, "NO_OFFSITE": 409}


def _authorize_backup(handler: BaseApiHandler, server_id: str, backup_id: str):
    """(auth data, backup config) if the user may handle this server's
    backups; otherwise the error has been sent and None is returned"""
    auth_data = handler.authenticate_user()
    if not auth_data:
        return None
    try:
        if server_id not in [str(x["server_id"]) for x in auth_data[0]]:
            raise Refused(400, "NOT_AUTHORIZED", "You cannot use this server")
        mask = handler.controller.server_perms.get_lowest_api_perm_mask(
            handler.controller.server_perms.get_user_permissions_mask(
                auth_data[4]["user_id"], server_id
            ),
            auth_data[5],
        )
        if EnumPermissionsServer.BACKUP not in (
            handler.controller.server_perms.get_permissions(mask)
        ):
            raise Refused(400, "NOT_AUTHORIZED", "You cannot handle its backups")
        try:
            backup_conf = handler.controller.management.get_backup_config(backup_id)
        except Exception as ex:  # pylint: disable=broad-exception-caught
            raise Refused(404, "BACKUP_NOT_FOUND", "There is no such backup") from ex
        if backup_conf["server_id"]["server_id"] != server_id:
            raise Refused(400, "ID_MISMATCH", "That backup is another server's")
    except Refused as ex:
        ex.send(handler)
        return None
    return auth_data, backup_conf


class ApiServersServerBackupsBackupOffsiteHandler(BaseApiHandler):
    """A backup's off-site copy: where it goes and how it went (GET),
    changing that (PATCH), and copying now or bringing a copy back (POST)"""

    def _copies(self):
        return self.controller.servers.backups_mgr.offsite

    async def get(self, server_id: str, backup_id: str):
        allowed = _authorize_backup(self, server_id, backup_id)
        if not allowed:
            return
        backup_conf = allowed[1]
        place = (
            HelperOffsite.get(backup_conf["offsite_id"])
            if backup_conf["offsite_id"]
            else None
        )
        data = {
            "targets": [
                {"target_id": t["target_id"], "name": t["name"], "kind": t["kind"]}
                for t in HelperOffsite.get_all()
            ],
            "offsite_id": backup_conf["offsite_id"] if place else "",
            "offsite_keep": backup_conf["offsite_keep"] or 0,
            "where": (
                offsite.describe(place["kind"], place["settings"]) if place else ""
            ),
            "status": last_status(backup_conf),
            "job": self._copies().job(backup_id),
            "fetched": self._copies().last_fetch(backup_id),
            "copies": None,
            "copies_error": None,
        }
        if place and self.get_argument("copies", "1") != "0":
            try:
                data["copies"] = await tornado.ioloop.IOLoop.current().run_in_executor(
                    None,
                    offsite.target(place["kind"], place["settings"]).list,
                    backup_id,
                )
            except offsite.OffsiteError as ex:
                data["copies_error"] = str(ex)
        self.finish_json(200, {"status": "ok", "data": data})

    def patch(self, server_id: str, backup_id: str):
        allowed = _authorize_backup(self, server_id, backup_id)
        if not allowed:
            return
        auth_data, backup_conf = allowed
        try:
            changes = self._changes(backup_conf)
        except Refused as ex:
            ex.send(self)
            return
        self.controller.management.update_backup_config(backup_id, changes)
        place = (
            HelperOffsite.get(changes["offsite_id"]) if changes["offsite_id"] else None
        )
        self.controller.management.add_to_audit_log(
            auth_data[4]["user_id"],
            f"Edited server {server_id}: backup {backup_conf['backup_name']} "
            + (
                f"copies to {place['name']}, keeping {changes['offsite_keep'] or 'all'}"
                if place
                else "is not copied off-site"
            ),
            server_id,
            self.get_remote_ip(),
        )
        self.finish_json(200, {"status": "ok"})

    def _changes(self, backup_conf: dict) -> dict:
        try:
            data = json.loads(self.request.body)
        except json.decoder.JSONDecodeError as ex:
            raise Refused(400, "INVALID_JSON", str(ex)) from ex
        if not isinstance(data, dict):
            raise Refused(400, "INVALID_JSON", "Send an object")
        target_id = data.get("offsite_id", backup_conf["offsite_id"] or "")
        keep = data.get("offsite_keep", backup_conf["offsite_keep"] or 0)
        if not isinstance(target_id, str) or (
            target_id and HelperOffsite.get(target_id) is None
        ):
            raise Refused(400, "INVALID_TARGET", "There is no such off-site storage")
        if target_id and backup_conf["backup_type"] != "zip_vault":
            raise Refused(
                400, "NOT_SUPPORTED", "Only zip backups can be copied off-site"
            )
        if (
            isinstance(keep, bool)
            or not isinstance(keep, int)
            or not 0 <= keep <= MAX_KEEP
        ):
            raise Refused(400, "INVALID_KEEP", "Keep a number of copies from 0 to 1000")
        changes = {"offsite_id": target_id, "offsite_keep": keep}
        if target_id != (backup_conf["offsite_id"] or ""):
            # How the last copy went is about the old place
            changes["offsite_status"] = ""
        return changes

    def post(self, server_id: str, backup_id: str):
        allowed = _authorize_backup(self, server_id, backup_id)
        if not allowed:
            return
        auth_data, backup_conf = allowed
        try:
            data = json.loads(self.request.body)
            action = data.get("action") if isinstance(data, dict) else None
        except json.decoder.JSONDecodeError:
            action = None
        try:
            if not backup_conf["offsite_id"] or not HelperOffsite.get(
                backup_conf["offsite_id"]
            ):
                raise Refused(409, "NO_OFFSITE", "Choose where to copy it first")
            if action == "copy":
                server = self.controller.servers.get_server_data_by_id(server_id)
                started = self._copies().start_copy(
                    server_id, server["server_name"], backup_id
                )
                self.finish_json(200, {"status": "ok", "data": {"started": started}})
                return
            if action != "fetch":
                raise Refused(400, "INVALID_ACTION", "action: copy or fetch")
            try:
                self._copies().start_fetch(backup_conf, data.get("name"))
            except offsite.OffsiteError as ex:
                raise Refused(FETCH_STATUS.get(ex.code, 400), ex.code, str(ex)) from ex
        except Refused as ex:
            ex.send(self)
            return
        self.controller.management.add_to_audit_log(
            auth_data[4]["user_id"],
            f"brought back the off-site copy {data.get('name')} of backup "
            f"{backup_conf['backup_name']}",
            server_id,
            self.get_remote_ip(),
        )
        self.finish_json(200, {"status": "ok", "data": {"started": True}})
