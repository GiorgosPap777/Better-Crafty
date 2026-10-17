"""Restart a server after warning the players in the game chat"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

# Server types whose console understands "say"
SUPPORTED_TYPES = ("minecraft-java", "minecraft-bedrock")
# The warning times the panel and the schedules offer, in minutes
CHOICES = (1, 2, 5, 10, 15, 30)
# Seconds before the restart at which players are warned again
WARN_AT = (1800, 900, 600, 300, 120, 60, 30, 10, 5, 4, 3, 2, 1)


def parse_minutes(value) -> int | None:
    """The warning time from an API value or a schedule's action_id, or None"""
    try:
        minutes = int(str(value))
    except (TypeError, ValueError):
        return None
    return minutes if minutes in CHOICES else None


def warning_times(total: int) -> list[int]:
    """When to warn, in seconds before the restart: at the start, then at
    each mark below it"""
    return [total] + [mark for mark in WARN_AT if mark < total]


def describe(seconds: int) -> str:
    if seconds >= 60 and seconds % 60 == 0:
        minutes = seconds // 60
        return f"{minutes} minute{'' if minutes == 1 else 's'}"
    return f"{seconds} second{'' if seconds == 1 else 's'}"


class RestartCountdown:
    """Warns the players with "say" at each mark, then restarts the server.

    Stops without restarting when it is cancelled or when the server stops
    in the meantime (someone stopped it by hand, or it crashed)."""

    def __init__(self, server, user_id: int, seconds: int, clock=time.monotonic):
        self.server = server
        self.user_id = user_id
        self.total = seconds
        self.clock = clock
        self.ends_at = clock() + seconds
        self.cancelled = threading.Event()
        # Set once the countdown has been cancelled or has claimed the restart,
        # so a cancel that comes in at the last second cannot be lost
        self.done = False
        self.lock = threading.Lock()
        self.thread = threading.Thread(
            target=self.run,
            name=f"restart_countdown_{server.server_id}",
            daemon=True,
        )

    def start(self):
        self.thread.start()

    def seconds_left(self) -> int:
        return max(0, round(self.ends_at - self.clock()))

    def wait_until(self, seconds_before: int) -> bool:
        """Sleeps until that many seconds before the restart; False if cancelled"""
        delay = self.ends_at - seconds_before - self.clock()
        if delay > 0:
            return not self.cancelled.wait(delay)
        return not self.cancelled.is_set()

    def cancel(self, announce: bool) -> bool:
        """False when it is too late: the restart has already begun"""
        with self.lock:
            if self.done:
                return False
            self.done = True
            self.cancelled.set()
        if announce and self.server.check_running():
            self.server.send_command("say Restart cancelled.")
        return True

    def claim_restart(self) -> bool:
        with self.lock:
            if self.done:
                return False
            self.done = True
            return True

    def count_down(self) -> bool:
        """Warns at each mark; True when the server should restart now"""
        for mark in warning_times(self.total):
            if not self.wait_until(mark):
                return False
            if not self.server.check_running():
                logger.info("Server stopped during the restart countdown")
                return False
            self.server.send_command(f"say Restarting in {describe(mark)}.")
        if not self.wait_until(0):
            return False
        return self.server.check_running() and self.claim_restart()

    def run(self):
        try:
            restart = self.count_down()
        finally:
            # Cleared before the restart, which takes a while, so the panel
            # stops showing the countdown as soon as it reaches zero
            self.server.restart_countdown_finished(self)
        if restart:
            self.server.restart_threaded_server(self.user_id)
