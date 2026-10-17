import datetime
import json
import os
import threading

import pytest
from peewee import SqliteDatabase

from app.classes.helpers import offsite
from app.classes.models.management import Backups
from app.classes.models.offsite import HelperOffsite, OffsiteTargets
from app.classes.models.servers import Servers
from app.classes.shared.offsite_copies import OffsiteCopies, last_status

MODELS = [Servers, Backups, OffsiteTargets]


@pytest.fixture(name="database")
def fixture_database(tmp_path):
    db = SqliteDatabase(tmp_path / "crafty.sqlite", pragmas={"journal_mode": "wal"})
    with db.bind_ctx(MODELS, bind_refs=False, bind_backrefs=False):
        db.create_tables(MODELS)
        Servers.insert(server_id="server-1", server_name="My Server").execute()
        yield db
    db.close()


class FakeBackupManager:
    """The parts of BackupManager the copier uses"""

    tz = datetime.timezone.utc

    def __init__(self, folder):
        self.folder = folder

    def backup_folder(self, _conf):
        return self.folder

    def list_backups(self, _conf, _server_id):
        return [{"path": name} for name in sorted(os.listdir(self.folder))]


def _wait(backup_id: str) -> None:
    for thread in threading.enumerate():
        if thread.name == f"offsite_{backup_id}":
            thread.join(10)


def _place(tmp_path) -> tuple:
    disk = tmp_path / "disk"
    disk.mkdir()
    offsite.FolderTarget({"path": str(disk)}).test()
    return disk, HelperOffsite.add("Second disk", "folder", {"path": str(disk)})


def _backup(folder, name: str, data: bytes) -> None:
    (folder / name).write_bytes(data)


@pytest.mark.usefixtures("database")
def test_removing_a_place_stops_its_backups(tmp_path) -> None:
    _, place = _place(tmp_path)
    Backups.insert(
        backup_id="b1", server_id="server-1", offsite_id=place, offsite_status="{}"
    ).execute()
    Backups.insert(backup_id="b2", server_id="server-1").execute()
    assert HelperOffsite.used_by(place) == 1
    assert [row["name"] for row in HelperOffsite.get_all()] == ["Second disk"]

    assert HelperOffsite.delete(place) == 1
    assert HelperOffsite.get(place) is None
    stopped = Backups.get_by_id("b1")
    assert (stopped.offsite_id, stopped.offsite_status) == ("", "")


@pytest.mark.usefixtures("database")
def test_copies_follow_new_backups(tmp_path) -> None:
    disk, place = _place(tmp_path)
    backups = tmp_path / "backups"
    backups.mkdir()
    Backups.insert(
        backup_id="b1", server_id="server-1", offsite_id=place, offsite_keep=2
    ).execute()
    copies = OffsiteCopies(None, FakeBackupManager(backups))

    # No backup yet: nothing to copy, nothing to say
    assert copies.start_copy("server-1", "My Server", "b1")
    _wait("b1")
    assert copies.job("b1") is None
    assert last_status(Backups.get_by_id("b1").__data__) is None

    for day in range(1, 5):
        _backup(backups, f"2026-10-0{day}_12-00-00.zip", bytes([day]) * day)
        assert copies.start_copy("server-1", "My Server", "b1")
        _wait("b1")
    folder = disk / "b1"
    # Only the newest backup is copied each time, and two are kept
    assert sorted(os.listdir(folder)) == [
        "My-Server_2026-10-03_12-00-00.zip",
        "My-Server_2026-10-04_12-00-00.zip",
    ]
    assert (folder / "My-Server_2026-10-04_12-00-00.zip").read_bytes() == b"\4" * 4
    status = last_status(Backups.get_by_id("b1").__data__)
    assert status["state"] == "ok"
    assert status["file"] == "2026-10-04_12-00-00.zip"
    assert status["target"] == "Second disk"

    # The disk is gone: the empty mount point has no marker
    (disk / offsite.MARKER).unlink()
    told = []
    copies._tell_failure = lambda *args: told.append(args)
    _backup(backups, "2026-10-05_12-00-00.zip", b"5")
    copies.start_copy("server-1", "My Server", "b1")
    _wait("b1")
    status = last_status(Backups.get_by_id("b1").__data__)
    assert status["state"] == "failed"
    assert "connected" in status["message"]
    assert told == [("server-1", "My Server", "Second disk")]


@pytest.mark.usefixtures("database")
def test_a_second_copy_waits_for_the_first(tmp_path) -> None:
    _, place = _place(tmp_path)
    Backups.insert(backup_id="b1", server_id="server-1", offsite_id=place).execute()
    copies = OffsiteCopies(None, FakeBackupManager(tmp_path))
    assert copies._claim("b1", "copy")
    # A backup finishes while copying: copied again afterwards
    assert not copies._claim("b1", "copy")
    assert copies.jobs["b1"]["again"] is True
    assert "again" not in copies.job("b1")
    assert not copies._claim("b1", "fetch", "x.zip")


@pytest.mark.usefixtures("database")
def test_bring_a_copy_back(tmp_path) -> None:
    disk, place = _place(tmp_path)
    backups = tmp_path / "backups"
    backups.mkdir()
    Backups.insert(backup_id="b1", server_id="server-1", offsite_id=place).execute()
    copies = OffsiteCopies(None, FakeBackupManager(backups))
    _backup(backups, "2026-10-01_12-00-00.zip", b"zip bytes")
    copies.start_copy("server-1", "My Server", "b1")
    _wait("b1")
    conf = Backups.get_by_id("b1").__data__

    with pytest.raises(offsite.OffsiteError) as caught:
        copies.start_fetch(conf, "My-Server_2026-10-01_12-00-00.zip")
    assert caught.value.code == "ALREADY_HERE"
    with pytest.raises(offsite.OffsiteError) as caught:
        copies.start_fetch(conf, "../crafty.sqlite")
    assert caught.value.code == "INVALID_NAME"

    (backups / "2026-10-01_12-00-00.zip").unlink()
    copies.start_fetch(conf, "My-Server_2026-10-01_12-00-00.zip")
    _wait("b1")
    back = backups / "2026-10-01_12-00-00.zip"
    assert back.read_bytes() == b"zip bytes"
    made = datetime.datetime(2026, 10, 1, 12, tzinfo=datetime.timezone.utc)
    assert back.stat().st_mtime == made.timestamp()
    assert copies.last_fetch("b1")["state"] == "ok"
    assert sorted(os.listdir(backups)) == ["2026-10-01_12-00-00.zip"]

    copies.start_fetch(conf, "My-Server_2026-09-01_12-00-00.zip")
    _wait("b1")
    assert copies.last_fetch("b1")["state"] == "failed"
    assert "not there" in copies.last_fetch("b1")["message"]
    assert sorted(os.listdir(backups)) == ["2026-10-01_12-00-00.zip"]
    assert (disk / "b1").is_dir()

    Backups.update(offsite_id="").execute()
    with pytest.raises(offsite.OffsiteError) as caught:
        copies.start_fetch(Backups.get_by_id("b1").__data__, back.name)
    assert caught.value.code == "NO_OFFSITE"


def test_last_status() -> None:
    assert last_status({"offsite_status": ""}) is None
    assert last_status({"offsite_status": "not json"}) is None
    assert last_status({"offsite_status": "[1]"}) is None
    status = {"state": "ok", "file": "a.zip"}
    assert last_status({"offsite_status": json.dumps(status)}) == status
