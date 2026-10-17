import json
import logging
from pathlib import Path

import tornado.ioloop

from app.classes.helpers import offsite
from app.classes.models.offsite import HelperOffsite
from app.classes.web.base_api_handler import BaseApiHandler
from app.classes.web.routes.api.refused import Refused

logger = logging.getLogger(__name__)

NAME_LENGTH = 60


def _superuser(handler: BaseApiHandler):
    """The auth data of a superuser; otherwise the error has been sent"""
    auth_data = handler.authenticate_user()
    if not auth_data:
        return None
    if not auth_data[3]:
        handler.finish_json(
            400,
            {
                "status": "error",
                "error": "NOT_AUTHORIZED",
                "error_data": handler.helper.translation.translate(
                    "validators", "insufficientPerms", auth_data[4]["lang"]
                ),
            },
        )
        return None
    return auth_data


def public_target(target: dict) -> dict:
    """A place to copy to as the browser sees it: no secret key"""
    return {
        "target_id": target["target_id"],
        "name": target["name"],
        "kind": target["kind"],
        "settings": offsite.public_settings(target["kind"], target["settings"]),
        "where": offsite.describe(target["kind"], target["settings"]),
        "used_by": HelperOffsite.used_by(target["target_id"]),
    }


class OffsiteForm:
    """Checks a place to copy to from the browser, then tests it"""

    def __init__(self, handler: BaseApiHandler, old: dict | None = None):
        self.handler = handler
        self.old = old

    def read(self, need_name: bool = True) -> tuple:
        try:
            data = json.loads(self.handler.request.body)
        except json.decoder.JSONDecodeError as ex:
            raise Refused(400, "INVALID_JSON", str(ex)) from ex
        if not isinstance(data, dict):
            raise Refused(400, "INVALID_JSON", "Send an object")
        name = data.get("name", "")
        if not isinstance(name, str) or not 0 < len(name.strip()) <= NAME_LENGTH:
            if need_name:
                raise Refused(400, "INVALID_NAME", "Give it a name of 1 to 60 letters")
            name = ""
        kind = data.get("kind")
        if kind not in offsite.KINDS:
            raise Refused(400, "INVALID_KIND", "The type must be folder or s3")
        old_settings = (
            self.old["settings"] if self.old and self.old["kind"] == kind else None
        )
        try:
            settings = offsite.clean_settings(kind, data.get("settings"), old_settings)
        except offsite.OffsiteError as ex:
            raise Refused(400, ex.code, str(ex)) from ex
        if kind == "folder":
            self._check_folder(settings["path"])
        return name.strip(), kind, settings

    def _check_folder(self, path: str) -> None:
        folder = Path(path).resolve()
        handler = self.handler
        for inside, why in (
            (
                handler.controller.management.get_master_server_dir(),
                "That folder is inside the servers folder",
            ),
            (handler.helper.backup_path, "That is where the backups are made"),
        ):
            if not inside:
                continue
            inside = Path(inside).resolve()
            if folder == inside or inside in folder.parents:
                raise Refused(400, "INVALID_SETTINGS", why)

    async def test(self, kind: str, settings: dict) -> list:
        """Write, read and delete a small file there. Returns warnings."""
        try:
            return await tornado.ioloop.IOLoop.current().run_in_executor(
                None,
                offsite.target(kind, settings).test,
                self.handler.helper.backup_path,
            )
        except offsite.OffsiteError as ex:
            raise Refused(400, ex.code, str(ex)) from ex
        except OSError as ex:
            raise Refused(400, "TEST_FAILED", str(ex)) from ex


class ApiCraftyOffsiteHandler(BaseApiHandler):
    """The places backups can be copied to (GET), and adding one (POST)"""

    def get(self):
        if not _superuser(self):
            return
        self.finish_json(
            200,
            {
                "status": "ok",
                "data": [public_target(t) for t in HelperOffsite.get_all()],
            },
        )

    async def post(self):
        auth_data = _superuser(self)
        if not auth_data:
            return
        form = OffsiteForm(self)
        try:
            name, kind, settings = form.read()
            warnings = await form.test(kind, settings)
        except Refused as ex:
            ex.send(self)
            return
        target_id = HelperOffsite.add(name, kind, settings)
        self.controller.management.add_to_audit_log(
            auth_data[4]["user_id"],
            f"added off-site storage {name} ({offsite.describe(kind, settings)})",
            None,
            self.get_remote_ip(),
        )
        self.finish_json(
            200,
            {
                "status": "ok",
                "data": {
                    "target": public_target(HelperOffsite.get(target_id)),
                    "warnings": warnings,
                },
            },
        )


class ApiCraftyOffsiteTargetHandler(BaseApiHandler):
    """Changing (PATCH) or removing (DELETE) a place to copy to"""

    async def patch(self, target_id: str):
        auth_data = _superuser(self)
        if not auth_data:
            return
        old = HelperOffsite.get(target_id)
        form = OffsiteForm(self, old)
        try:
            if old is None:
                raise Refused(404, "NOT_FOUND", "There is no such off-site storage")
            name, kind, settings = form.read()
            warnings = await form.test(kind, settings)
        except Refused as ex:
            ex.send(self)
            return
        HelperOffsite.update(target_id, name, kind, settings)
        self.controller.management.add_to_audit_log(
            auth_data[4]["user_id"],
            f"changed off-site storage {name} ({offsite.describe(kind, settings)})",
            None,
            self.get_remote_ip(),
        )
        self.finish_json(
            200,
            {
                "status": "ok",
                "data": {
                    "target": public_target(HelperOffsite.get(target_id)),
                    "warnings": warnings,
                },
            },
        )

    def delete(self, target_id: str):
        auth_data = _superuser(self)
        if not auth_data:
            return
        old = HelperOffsite.get(target_id)
        if old is None:
            Refused(404, "NOT_FOUND", "There is no such off-site storage").send(self)
            return
        stopped = HelperOffsite.delete(target_id)
        self.controller.management.add_to_audit_log(
            auth_data[4]["user_id"],
            f"removed off-site storage {old['name']}; {stopped} backups stop copying"
            " there (the copies stay)",
            None,
            self.get_remote_ip(),
        )
        self.finish_json(200, {"status": "ok", "data": {"stopped": stopped}})


class ApiCraftyOffsiteTestHandler(BaseApiHandler):
    """Try a place to copy to without saving it. With target_id, an empty
    secret key means the saved one."""

    async def post(self):
        if not _superuser(self):
            return
        try:
            target_id = json.loads(self.request.body).get("target_id")
        except (json.decoder.JSONDecodeError, AttributeError):
            target_id = None
        old = HelperOffsite.get(target_id) if isinstance(target_id, str) else None
        form = OffsiteForm(self, old)
        try:
            _name, kind, settings = form.read(need_name=False)
            warnings = await form.test(kind, settings)
        except Refused as ex:
            ex.send(self)
            return
        self.finish_json(200, {"status": "ok", "data": {"warnings": warnings}})
