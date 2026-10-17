"""Copy each new zip backup to its off-site place, and bring copies back"""

import datetime
import json
import logging
import os
import shutil
import threading
import time
from pathlib import Path

from app.classes.helpers import offsite
from app.classes.models.management import HelpersManagement
from app.classes.models.offsite import HelperOffsite
from app.classes.models.server_permissions import PermissionsServers
from app.classes.models.users import HelperUsers
from app.classes.shared.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

# Disk space left free when a copy is brought back
SPARE_SPACE = 64 * 1024 * 1024


def last_status(backup_conf: dict) -> dict | None:
    """How the last copy went: state (ok or failed), file, target, time and
    message; None before the first copy"""
    try:
        status = json.loads(backup_conf.get("offsite_status") or "null")
    except ValueError:
        return None
    return status if isinstance(status, dict) else None


class OffsiteCopies:
    """Copies run one at a time per backup config, in the background. A
    backup that finishes while its config is still copying gets copied when
    that copy is done (only the newest one, if several finished)."""

    def __init__(self, helper, backup_mgr):
        self.helper = helper
        self.backup_mgr = backup_mgr
        self.lock = threading.Lock()
        # Running jobs by backup id: action (copy or fetch), file, percent
        self.jobs = {}
        # How the last fetch of each backup config went
        self.fetched = {}

    def job(self, backup_id: str) -> dict | None:
        with self.lock:
            job = self.jobs.get(backup_id)
            if not job:
                return None
            return {key: value for key, value in job.items() if key != "again"}

    def last_fetch(self, backup_id: str) -> dict | None:
        with self.lock:
            return self.fetched.get(backup_id)

    def _claim(self, backup_id: str, action: str, name: str | None = None) -> bool:
        with self.lock:
            job = self.jobs.get(backup_id)
            if job:
                if action == "copy" and job["action"] == "copy":
                    job["again"] = True
                return False
            self.jobs[backup_id] = {
                "action": action,
                "file": name,
                "percent": 0,
                "again": False,
            }
            return True

    def _set(self, backup_id: str, **values) -> None:
        with self.lock:
            if backup_id in self.jobs:
                self.jobs[backup_id].update(values)

    def _progress(self, backup_id: str):
        def update(done: int, total: int) -> None:
            self._set(backup_id, percent=int(done * 100 / total) if total else 100)

        return update

    def start_copy(self, server_id: str, server_name: str, backup_id: str) -> bool:
        """Copy the newest backup off-site, in the background. False when a
        copy was already running (it copies the newest again afterwards)."""
        if not self._claim(backup_id, "copy"):
            return False
        threading.Thread(
            target=self._copy_loop,
            args=(server_id, server_name, backup_id),
            name=f"offsite_{backup_id}",
            daemon=True,
        ).start()
        return True

    def _copy_loop(self, server_id: str, server_name: str, backup_id: str) -> None:
        try:
            while True:
                self._copy_newest(server_id, server_name, backup_id)
                with self.lock:
                    job = self.jobs[backup_id]
                    if not job["again"]:
                        break
                    job.update(again=False, percent=0, file=None)
        finally:
            with self.lock:
                self.jobs.pop(backup_id, None)

    def _copy_newest(self, server_id: str, server_name: str, backup_id: str) -> None:
        try:
            conf = HelpersManagement.get_backup_config(backup_id)
        except Exception:  # pylint: disable=broad-exception-caught
            # The backup config was deleted meanwhile
            return
        place = HelperOffsite.get(conf["offsite_id"]) if conf["offsite_id"] else None
        if place is None or conf["backup_type"] != "zip_vault":
            return
        files = self.backup_mgr.list_backups(conf, server_id)
        if not files:
            return
        name = files[-1]["path"]
        self._set(backup_id, file=name)
        status = {"target": place["name"], "file": name}
        try:
            storage = offsite.target(place["kind"], place["settings"])
            if not offsite.has_copy(storage.list(backup_id), name):
                logger.info(
                    f"Copying backup {name} of {server_name} to {place['name']}"
                )
                storage.put(
                    Path(self.backup_mgr.backup_folder(conf), name),
                    backup_id,
                    offsite.copy_name(server_name, name),
                    self._progress(backup_id),
                )
            removed = offsite.keep_newest(storage, backup_id, conf["offsite_keep"])
            if removed:
                logger.info(f"Removed old off-site copies: {', '.join(removed)}")
            status["state"] = "ok"
        except Exception as ex:  # pylint: disable=broad-exception-caught
            if not isinstance(ex, offsite.OffsiteError):
                logger.exception(f"Off-site copy of {name} failed")
            logger.warning(f"Off-site copy of {name} to {place['name']} failed: {ex}")
            status.update(state="failed", message=str(ex))
            self._tell_failure(server_id, server_name, place["name"])
        status["time"] = time.time()
        HelpersManagement.update_backup_config(
            backup_id, {"offsite_status": json.dumps(status)}
        )

    def _tell_failure(self, server_id: str, server_name: str, place: str) -> None:
        for user in PermissionsServers.get_server_user_list(server_id):
            WebSocketManager().broadcast_user(
                user,
                "notification",
                self.helper.translation.translate(
                    "notify", "offsiteFailed", HelperUsers.get_user_lang_by_id(user)
                ).format(server_name, place),
            )

    def start_fetch(self, backup_conf: dict, name: str) -> None:
        """Bring a copy back into the backup folder, in the background, so it
        can be restored like any other backup"""
        name = offsite.fetch_name(name)
        place = (
            HelperOffsite.get(backup_conf["offsite_id"])
            if backup_conf["offsite_id"]
            else None
        )
        if place is None:
            raise offsite.OffsiteError(
                "NO_OFFSITE", "This backup is not copied off-site"
            )
        local = Path(
            self.backup_mgr.backup_folder(backup_conf), offsite.local_name(name)
        )
        if local.exists():
            raise offsite.OffsiteError("ALREADY_HERE", "That backup is already here")
        if not self._claim(backup_conf["backup_id"], "fetch", name):
            raise offsite.OffsiteError(
                "OFFSITE_BUSY", "Wait until the copy that is running has finished"
            )
        threading.Thread(
            target=self._fetch,
            args=(backup_conf["backup_id"], place, name, local),
            name=f"offsite_{backup_conf['backup_id']}",
            daemon=True,
        ).start()

    def _fetch(self, backup_id: str, place: dict, name: str, local: Path) -> None:
        part = local.with_name(local.name + ".part")
        result = {"file": name, "local": local.name}
        try:
            storage = offsite.target(place["kind"], place["settings"])
            copy = next((c for c in storage.list(backup_id) if c["name"] == name), None)
            if copy is None:
                raise offsite.OffsiteError(
                    "NOT_FOUND", "That copy is not there any more"
                )
            local.parent.mkdir(parents=True, exist_ok=True)
            if copy["size"] + SPARE_SPACE > shutil.disk_usage(local.parent).free:
                raise offsite.OffsiteError(
                    "OUT_OF_SPACE", "There is not enough free disk space for it"
                )
            storage.get(backup_id, name, part, self._progress(backup_id))
            made = self._backup_time(local.name, copy["time"])
            os.utime(part, (made, made))
            os.replace(part, local)
            result["state"] = "ok"
        except Exception as ex:  # pylint: disable=broad-exception-caught
            if not isinstance(ex, offsite.OffsiteError):
                logger.exception(f"Could not bring back {name}")
            part.unlink(missing_ok=True)
            result.update(state="failed", message=str(ex))
        finally:
            result["time"] = time.time()
            with self.lock:
                self.fetched[backup_id] = result
                self.jobs.pop(backup_id, None)

    def _backup_time(self, name: str, fallback: float) -> float:
        """When a backup was made, from its name, so that it sorts in its
        place among the others"""
        try:
            made = datetime.datetime.strptime(name, "%Y-%m-%d_%H-%M-%S.zip")
            return made.replace(tzinfo=self.backup_mgr.tz).timestamp()
        except (ValueError, TypeError):
            return fallback or time.time()
