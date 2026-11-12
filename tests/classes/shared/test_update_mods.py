"""The scheduled "Update mods and plugins" task on a server."""

import pytest

from app.classes.shared import server as server_module
from app.classes.shared.server import ServerInstance


class FakeStats:
    def __init__(self, events):
        self.events = events

    @staticmethod
    def get_latest_server_stats():
        return {"version": "Paper 1.21.1"}

    def set_update(self, value):
        self.events.append(f"updating={value}")


class FakeHelper:
    root_dir = "/root-dir"


class FakeServer:
    server_id = "s1"
    name = "Survival"
    helper = FakeHelper()

    def __init__(self, running=True, backup="ok"):
        self.events = []
        self.notices = []
        self.running = running
        self.backup = backup
        self.stats_helper = FakeStats(self.events)

    def check_running(self):
        return self.running

    def cancel_restart_countdown(self, announce=True):
        self.events.append(f"cancel countdown announce={announce}")

    def stop_threaded_server(self):
        self.events.append("stop")
        self.running = False

    def backup_server(self, backup_id):
        self.events.append(f"backup {backup_id}")
        return {"backup_status": self.backup, "backup_error": "disk full"}

    def run_threaded_server(self, user_id):
        self.events.append(f"start by {user_id}")

    def _mods_notice(self, message, audit=False):
        self.notices.append((message, audit))


@pytest.fixture(name="patched")
def fixture_patched(monkeypatch):
    found = {"count": 2, "backup": {"backup_id": "b1"}}
    calls = []
    monkeypatch.setattr(
        server_module.HelperServers,
        "get_server_data_by_id",
        staticmethod(lambda server_id: {"server_id": server_id}),
    )
    monkeypatch.setattr(
        server_module.HelperUsers,
        "get_user_id_by_name",
        staticmethod(lambda name: f"<{name}>"),
    )

    def default_backup(_server_id):
        if found["backup"] is None:
            raise IndexError
        return found["backup"]

    monkeypatch.setattr(
        server_module.HelpersManagement,
        "get_default_server_backup",
        staticmethod(default_backup),
    )
    monkeypatch.setattr(server_module.mod_updates, "check", lambda *args: {})
    monkeypatch.setattr(
        server_module.mod_updates, "count", lambda state: found["count"]
    )

    def update_all(root, settings, version):
        calls.append((root, settings["server_id"], version))
        return {"updated": ["a-2.jar", "t-3.zip"], "failed": ["B: gone"]}

    monkeypatch.setattr(server_module.mod_updates, "update_all", update_all)
    found["calls"] = calls
    return found


def test_backs_up_updates_and_starts_again(patched):
    svr = FakeServer()
    ServerInstance.update_mods(svr, 1)
    assert svr.events == [
        "cancel countdown announce=False",
        "stop",
        "updating=True",
        "backup b1",
        "updating=False",
        "start by <system>",
    ]
    assert patched["calls"] == [("/root-dir", "s1", "Paper 1.21.1")]
    assert svr.notices == [
        ("Updated on Survival: a-2.jar, t-3.zip. Not updated: B: gone", True)
    ]


def test_a_stopped_server_stays_stopped(patched):
    svr = FakeServer(running=False)
    ServerInstance.update_mods(svr, 1)
    assert svr.events == ["updating=True", "backup b1", "updating=False"]
    assert patched["calls"]


def test_nothing_to_update_does_nothing(patched):
    patched["count"] = 0
    svr = FakeServer()
    ServerInstance.update_mods(svr, 1)
    assert not svr.events
    assert not patched["calls"]
    assert svr.notices == [("Survival: no mod, plugin or data pack updates", False)]


def test_no_backup_set_up_updates_nothing(patched):
    patched["backup"] = None
    svr = FakeServer()
    ServerInstance.update_mods(svr, 1)
    assert not svr.events
    assert not patched["calls"]
    assert "no backup set up" in svr.notices[0][0]


def test_a_failed_backup_updates_nothing_and_starts_again(patched):
    svr = FakeServer(backup="failed")
    ServerInstance.update_mods(svr, 1)
    assert not patched["calls"]
    assert svr.events[-2:] == ["updating=False", "start by <system>"]
    assert svr.notices == [
        ("The backup of Survival failed, so its mods were not updated: disk full", True)
    ]
