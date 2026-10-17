import threading

import pytest

from app.classes.shared.restart_countdown import (
    RestartCountdown,
    describe,
    parse_minutes,
    warning_times,
)
from app.classes.shared.server import ServerInstance


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FakeEvent:
    """threading.Event whose wait() moves the fake clock on instead of sleeping"""

    def __init__(self, clock):
        self.clock = clock
        self.flag = False

    def wait(self, timeout):
        if not self.flag:
            self.clock.now += timeout
        return self.flag

    def set(self):
        self.flag = True

    def is_set(self):
        return self.flag


class FakeServer:
    server_id = "test-server"

    def __init__(self, clock):
        self.clock = clock
        self.running = True
        self.events = []
        self.on_say = None

    def check_running(self):
        return self.running

    def send_command(self, command):
        self.events.append((self.clock.now, command))
        if self.on_say:
            self.on_say(command)

    def restart_threaded_server(self, user_id):
        self.events.append((self.clock.now, f"restart by {user_id}"))

    def restart_countdown_finished(self, _countdown):
        self.events.append((self.clock.now, "finished"))


def make_countdown(seconds):
    clock = FakeClock()
    server = FakeServer(clock)
    countdown = RestartCountdown(server, 7, seconds, clock=clock)
    countdown.cancelled = FakeEvent(clock)
    return server, countdown


@pytest.mark.parametrize(
    "value, expected",
    [("5", 5), (5, 5), ("30", 30), ("7", None), ("", None), (None, None)],
)
def test_parse_minutes(value, expected) -> None:
    assert parse_minutes(value) == expected


def test_parse_minutes_rejects_backup_ids() -> None:
    assert parse_minutes("6f1e4a52-2c55-4b8e-9d7a-0d1c2b3a4f5e") is None


def test_warning_times() -> None:
    assert warning_times(120) == [120, 60, 30, 10, 5, 4, 3, 2, 1]
    assert warning_times(1800)[:3] == [1800, 900, 600]


@pytest.mark.parametrize(
    "seconds, text",
    [(300, "5 minutes"), (60, "1 minute"), (30, "30 seconds"), (1, "1 second")],
)
def test_describe(seconds, text) -> None:
    assert describe(seconds) == text


def test_countdown_warns_then_restarts() -> None:
    server, countdown = make_countdown(120)
    countdown.run()
    assert server.events == [
        (0, "say Restarting in 2 minutes."),
        (60, "say Restarting in 1 minute."),
        (90, "say Restarting in 30 seconds."),
        (110, "say Restarting in 10 seconds."),
        (115, "say Restarting in 5 seconds."),
        (116, "say Restarting in 4 seconds."),
        (117, "say Restarting in 3 seconds."),
        (118, "say Restarting in 2 seconds."),
        (119, "say Restarting in 1 second."),
        # The panel stops showing the countdown before the slow restart
        (120, "finished"),
        (120, "restart by 7"),
    ]


def test_cancel_stops_the_countdown() -> None:
    server, countdown = make_countdown(120)
    results = []

    def cancel_at_one_minute(command):
        if command == "say Restarting in 1 minute.":
            results.append(countdown.cancel(announce=True))

    server.on_say = cancel_at_one_minute
    countdown.run()
    assert results == [True]
    assert [text for _, text in server.events] == [
        "say Restarting in 2 minutes.",
        "say Restarting in 1 minute.",
        "say Restart cancelled.",
        "finished",
    ]


def test_server_stopped_during_the_countdown() -> None:
    server, countdown = make_countdown(120)

    def stop_at_one_minute(command):
        if command == "say Restarting in 1 minute.":
            server.running = False

    server.on_say = stop_at_one_minute
    countdown.run()
    assert [text for _, text in server.events] == [
        "say Restarting in 2 minutes.",
        "say Restarting in 1 minute.",
        "finished",
    ]


def test_cancel_is_too_late_once_the_restart_began() -> None:
    server, countdown = make_countdown(60)
    assert countdown.claim_restart()
    assert countdown.cancel(announce=True) is False
    assert not server.events


def test_seconds_left() -> None:
    _server, countdown = make_countdown(300)
    countdown.clock.now = 120.4
    assert countdown.seconds_left() == 180
    countdown.clock.now = 400
    assert countdown.seconds_left() == 0


class Server:
    """The countdown methods of ServerInstance on a server that needs no setup"""

    server_id = "test-server"
    start_restart_countdown = ServerInstance.start_restart_countdown
    cancel_restart_countdown = ServerInstance.cancel_restart_countdown
    restart_countdown_finished = ServerInstance.restart_countdown_finished
    restart_countdown_left = ServerInstance.restart_countdown_left
    can_warn_players = ServerInstance.can_warn_players

    def __init__(self, server_type="minecraft-java", online=3, running=True):
        self.settings = {"type": server_type}
        self.online = online
        self.running = running
        self.restart_countdown = None
        self._countdown_lock = threading.Lock()
        self.commands = []

    def check_running(self):
        return self.running

    def players_online(self):
        return self.online

    def send_command(self, command):
        self.commands.append(command)


@pytest.fixture(autouse=True)
def no_countdown_threads(monkeypatch):
    monkeypatch.setattr(RestartCountdown, "start", lambda self: None)


@pytest.mark.parametrize(
    "server",
    [
        Server(online=0),
        Server(running=False),
        Server(server_type="steam_cmd"),
    ],
    ids=["nobody online", "not running", "no game chat"],
)
def test_restart_at_once_when_there_is_nobody_to_warn(server) -> None:
    assert server.start_restart_countdown(1, 5) == 0
    assert server.restart_countdown_left() is None


def test_start_and_cancel_from_the_server() -> None:
    server = Server()
    # The player count is unknown when the ping fails: warn anyway
    server.online = None
    assert server.start_restart_countdown(1, 5) == 300
    assert server.restart_countdown_left() == 300

    first = server.restart_countdown
    assert server.start_restart_countdown(1, 1) == 60
    # Starting again replaces the old countdown without telling the players
    assert first.cancelled.is_set()
    assert not server.commands

    assert server.cancel_restart_countdown() is True
    assert server.commands == ["say Restart cancelled."]
    assert server.restart_countdown_left() is None
    assert server.cancel_restart_countdown() is False
