import base64
import io
import json
import time

import pytest
import requests
from PIL import Image

from app.classes.helpers import player_skins
from app.classes.helpers.player_skins import PlayerSkins, default_skin, normalise

NOTCH = "069a79f4-44e9-4726-a5be-fca90e38aaf5"
# Version 3: an offline-mode player, never looked up at Mojang
OFFLINE = "00000000-0000-3000-0000-000000003010"
SKIN_URL = "http://textures.minecraft.net/texture/abc123"


def _png(size=(64, 64), color=(10, 20, 30, 255), fmt="PNG"):
    data = io.BytesIO()
    Image.new("RGBA", size, color).save(data, fmt)
    return data.getvalue()


def _textures(url=SKIN_URL, slim=False):
    skin = {"url": url}
    if slim:
        skin["metadata"] = {"model": "slim"}
    value = json.dumps({"textures": {"SKIN": skin}}).encode()
    return {"properties": [{"name": "textures", "value": base64.b64encode(value)}]}


class FakeResponse:
    def __init__(self, status=200, body=None, data=b""):
        self.status_code = status
        self.body = body
        self.data = data

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def iter_content(self, size):
        for start in range(0, len(self.data), size):
            yield self.data[start : start + size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture(name="config")
def fixture_config(tmp_path, monkeypatch):
    """A config folder with item pictures holding two default skins."""
    icons = tmp_path / "item_icons"
    icons.mkdir()
    (icons / "info.json").write_text(json.dumps({"version": "1", "count": 1}))
    for name in ("_skin_slim_alex", "_skin_wide_sunny"):
        (icons / f"{name}.png").write_bytes(_png(color=(1, 2, 3, 255)))
    monkeypatch.setattr(PlayerSkins, "_instances", {})
    return tmp_path


def _mojang(monkeypatch, profile, skin=None, calls=None):
    def get(url, **kwargs):
        if calls is not None:
            calls.append(url)
        if url.startswith("https://sessionserver.mojang.com/"):
            return (
                profile
                if isinstance(profile, FakeResponse)
                else FakeResponse(body=profile)
            )
        assert url == "https://textures.minecraft.net/texture/abc123"
        assert kwargs.get("stream")
        return skin

    monkeypatch.setattr(player_skins.requests, "get", get)


def test_default_skin_matches_the_game():
    # Worked out with java.util.UUID.hashCode()
    assert default_skin(NOTCH.replace("-", "")) == ("alex", "slim")
    assert default_skin("80000000000000000000000000000000") == ("sunny", "wide")


def test_old_skins_get_the_new_layout():
    old = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    old.paste((255, 0, 0, 255), (4, 20, 8, 32))  # front of the right leg
    old.paste((0, 0, 255, 255), (32, 0, 64, 32))  # a solid hat, as the game checks
    img = normalise(old)
    assert img.size == (64, 64)
    # The left leg is the right one, mirrored
    assert img.getpixel((20, 52)) == (255, 0, 0, 255)
    # A solid hat on an old skin is hidden
    assert img.getpixel((40, 8))[3] == 0
    # The head is always opaque
    assert img.getpixel((8, 8))[3] == 255


def test_normalise_refuses_other_sizes():
    with pytest.raises(ValueError):
        normalise(Image.new("RGBA", (32, 32)))


def test_no_pictures_no_skin(tmp_path, monkeypatch):
    monkeypatch.setattr(PlayerSkins, "_instances", {})
    assert PlayerSkins.get(tmp_path).skin(NOTCH) is None


def test_bad_uuid(config):
    with pytest.raises(ValueError):
        PlayerSkins.get(config).skin("../../etc/passwd")


def test_offline_player_gets_default_without_asking(config, monkeypatch):
    calls = []
    _mojang(monkeypatch, {}, calls=calls)
    data, model = PlayerSkins.get(config).skin(OFFLINE)
    assert model == "wide" and Image.open(io.BytesIO(data)).size == (64, 64)
    assert not calls


def test_own_skin_is_fetched_and_kept(config, monkeypatch):
    calls = []
    _mojang(
        monkeypatch,
        _textures(slim=False),
        FakeResponse(data=_png(color=(9, 9, 9, 255))),
        calls,
    )
    skins = PlayerSkins.get(config)
    data, model = skins.skin(NOTCH)
    assert model == "wide"
    assert Image.open(io.BytesIO(data)).getpixel((8, 8)) == (9, 9, 9, 255)
    assert len(calls) == 2
    # Kept: no second request
    assert skins.skin(NOTCH)[0] == data
    assert len(calls) == 2
    assert (config / "player_skins" / f"{NOTCH.replace('-', '')}.png").is_file()


def test_slim_skin(config, monkeypatch):
    _mojang(monkeypatch, _textures(slim=True), FakeResponse(data=_png()))
    assert PlayerSkins.get(config).skin(NOTCH)[1] == "slim"


def test_account_without_skin_gets_default(config, monkeypatch):
    _mojang(monkeypatch, FakeResponse(status=204))
    data, model = PlayerSkins.get(config).skin(NOTCH)
    assert model == "slim"
    assert Image.open(io.BytesIO(data)).getpixel((8, 8)) == (1, 2, 3, 255)
    info = json.loads(
        (config / "player_skins" / f"{NOTCH.replace('-', '')}.json").read_text()
    )
    assert info["default"] is True


@pytest.mark.parametrize(
    "profile, skin",
    [
        # Not Mojang's texture server
        (_textures(url="http://evil.example/texture/abc123"), None),
        # Too big
        (_textures(), FakeResponse(data=b"x" * (player_skins.MAX_BYTES + 1))),
        # Not a PNG, or not a skin
        (_textures(), FakeResponse(data=_png(fmt="GIF"))),
        (_textures(), FakeResponse(data=_png(size=(32, 32)))),
        (_textures(), FakeResponse(data=b"not a picture")),
        # Mojang is down
        (FakeResponse(status=503), None),
    ],
)
def test_bad_answers_fall_back_to_default(config, monkeypatch, profile, skin):
    _mojang(monkeypatch, profile, skin)
    data, model = PlayerSkins.get(config).skin(NOTCH)
    assert model == "slim"
    assert Image.open(io.BytesIO(data)).getpixel((8, 8)) == (1, 2, 3, 255)


def test_failure_is_not_retried_at_once(config, monkeypatch):
    calls = []

    def down(url, **_kwargs):
        calls.append(url)
        raise requests.ConnectionError("no internet")

    monkeypatch.setattr(player_skins.requests, "get", down)
    skins = PlayerSkins.get(config)
    skins.skin(NOTCH)
    skins.skin(NOTCH)
    assert len(calls) == 1


def test_stale_skin_is_used_when_mojang_fails(config, monkeypatch):
    _mojang(monkeypatch, _textures(), FakeResponse(data=_png(color=(9, 9, 9, 255))))
    skins = PlayerSkins.get(config)
    first = skins.skin(NOTCH)
    info_path = config / "player_skins" / f"{NOTCH.replace('-', '')}.json"
    info = json.loads(info_path.read_text())
    info["checked"] = time.time() - player_skins.FRESH_SECONDS - 1
    info_path.write_text(json.dumps(info))

    def down(url, **_kwargs):
        raise requests.ConnectionError("no internet")

    monkeypatch.setattr(player_skins.requests, "get", down)
    assert skins.skin(NOTCH) == first


def test_pictures_without_default_skins(config, monkeypatch):
    for path in (config / "item_icons").glob("_skin_*"):
        path.unlink()
    monkeypatch.setattr(player_skins.requests, "get", None)
    assert PlayerSkins.get(config).skin(OFFLINE) is None
