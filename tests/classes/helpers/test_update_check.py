import json
from pathlib import Path

import pytest
import requests

from app.classes.helpers import helpers
from app.classes.helpers.helpers import Helpers

VERSION_FILE = Path(__file__).parents[3] / "app" / "config" / "version.json"


class FakeHelper:
    FORK_REPO = Helpers.FORK_REPO

    def __init__(self, version):
        self.version = version

    def get_fork_version(self):
        return self.version


class FakeResponse:
    def __init__(self, status, body=None):
        self.status_code = status
        self.body = body

    def json(self):
        return self.body


def _check(monkeypatch, version, status=200, tag="v1.2.0"):
    calls = []

    def fake_get(url, **_kwargs):
        calls.append(url)
        return FakeResponse(status, {"tag_name": tag})

    monkeypatch.setattr(helpers, "get", fake_get)
    result = Helpers.check_remote_version(FakeHelper(version))
    assert calls == [
        "https://api.github.com/repos/GiorgosPap777/Better-Crafty/releases/latest"
    ]
    return result


def test_newer_release_found(monkeypatch):
    assert str(_check(monkeypatch, "1.0.0")) == "1.2.0"


@pytest.mark.parametrize("version", ["1.2.0", "1.3.0"])
def test_same_or_older_release_ignored(monkeypatch, version):
    assert _check(monkeypatch, version) is False


def test_no_release_yet(monkeypatch):
    assert _check(monkeypatch, "1.0.0", status=404) is False


def test_bad_tag_or_network_error(monkeypatch):
    assert _check(monkeypatch, "1.0.0", tag="nightly") is False

    def fail(url, **_kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(helpers, "get", fail)
    assert Helpers.check_remote_version(FakeHelper("1.0.0")) is False


def test_version_file_has_both_versions():
    data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    assert {"major", "minor", "sub", "better_crafty"} <= data.keys()
    assert data["better_crafty"].count(".") == 2
