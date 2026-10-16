import hashlib
import io
import json
import zipfile

import pytest
from PIL import Image

from app.classes.helpers import item_icons
from app.classes.helpers.item_icons import Assets, ItemIcons, render_all, render_item

RED = (200, 30, 30, 255)
WHITE = (255, 255, 255, 255)


def _png(color, size=(16, 16)):
    data = io.BytesIO()
    Image.new("RGBA", size, color).save(data, "PNG")
    return data.getvalue()


def _cube(texture="#all"):
    faces = {
        side: {"texture": texture}
        for side in ("down", "up", "north", "south", "west", "east")
    }
    return [{"from": [0, 0, 0], "to": [16, 16, 16], "faces": faces}]


# A tiny stand-in for the client jar: path under assets/minecraft -> content
FILES = {
    "models/item/generated.json": {"parent": "builtin/generated"},
    "models/block/block.json": {
        "gui_light": "side",
        "display": {
            "gui": {
                "rotation": [30, 225, 0],
                "translation": [0, 0, 0],
                "scale": [0.625] * 3,
            }
        },
    },
    "models/block/cube_all.json": {"parent": "block/block", "elements": _cube()},
    "models/block/white.json": {
        "parent": "minecraft:block/cube_all",
        "textures": {"all": "minecraft:block/white"},
    },
    # A face naming its texture variable without "#"
    "models/block/plain.json": {
        "parent": "block/block",
        "textures": {"all": "block/white"},
        "elements": _cube("all"),
    },
    "models/item/apple.json": {
        "parent": "minecraft:item/generated",
        "textures": {"layer0": "minecraft:item/apple"},
    },
    "models/item/leaf.json": {
        "parent": "item/generated",
        "textures": {"layer0": "item/white"},
    },
    "models/item/no_texture.json": {
        "parent": "item/generated",
        "textures": {"layer0": "item/missing"},
    },
    "items/apple.json": {"model": {"type": "minecraft:model", "model": "item/apple"}},
    "items/white_block.json": {"model": {"type": "model", "model": "block/white"}},
    "items/plain.json": {"model": {"type": "model", "model": "minecraft:block/plain"}},
    "items/leaf.json": {
        "model": {
            "type": "model",
            "model": "item/leaf",
            "tints": [{"type": "minecraft:constant", "value": 0x22CC22}],
        }
    },
    # Inventory pictures use the "gui" case of a select
    "items/picked.json": {
        "model": {
            "type": "select",
            "property": "display_context",
            "cases": [
                {"when": "ground", "model": {"type": "model", "model": "item/leaf"}},
                {
                    "when": ["fixed", "gui"],
                    "model": {"type": "model", "model": "item/apple"},
                },
            ],
            "fallback": {"type": "model", "model": "item/leaf"},
        }
    },
    "items/conditional.json": {
        "model": {
            "type": "condition",
            "property": "using_item",
            "on_true": {"type": "model", "model": "item/leaf"},
            "on_false": {"type": "model", "model": "item/apple"},
        }
    },
    "items/both.json": {
        "model": {
            "type": "composite",
            "models": [
                {"type": "model", "model": "block/white"},
                {"type": "model", "model": "item/apple"},
            ],
        }
    },
    "items/no_texture.json": {"model": {"type": "model", "model": "item/no_texture"}},
    "items/no_model.json": {"model": {"type": "model", "model": "item/nothing"}},
    "items/loop.json": {"model": {"type": "model", "model": "item/loop"}},
    "models/item/loop.json": {"parent": "item/loop"},
    "items/Bad Name.json": {"model": {"type": "model", "model": "item/apple"}},
    "items/broken.json": "{not json",
    "textures/item/apple.png": _png(RED),
    "textures/item/white.png": _png(WHITE),
    "textures/block/white.png": _png(WHITE),
    "textures/gui/sprites/hud/heart/full.png": _png(RED, (9, 9)),
}


def _jar(path=None):
    data = io.BytesIO() if path is None else path
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("assets/minecraft/items/", "")
        for name, content in FILES.items():
            if isinstance(content, dict):
                content = json.dumps(content)
            archive.writestr("assets/minecraft/" + name, content)
    return data


@pytest.fixture(name="assets")
def fixture_assets():
    with zipfile.ZipFile(_jar()) as archive:
        yield Assets(archive)


def test_flat_item_fills_the_slot(assets):
    picture = render_item(assets, "apple")
    assert picture.size == (64, 64)
    assert picture.getpixel((32, 32)) == RED
    assert picture.getpixel((0, 0)) == RED


def test_tint_colours_a_layer(assets):
    assert render_item(assets, "leaf").getpixel((32, 32)) == (0x22, 0xCC, 0x22, 255)


def test_block_is_drawn_lit_from_the_top_left(assets):
    picture = render_item(assets, "white_block")
    assert picture.size == (64, 64)
    # Corners of the slot stay clear around the cube
    assert picture.getpixel((1, 1))[3] == 0
    top = picture.getpixel((32, 14))
    left = picture.getpixel((18, 38))
    right = picture.getpixel((46, 38))
    assert top[3] == left[3] == right[3] == 255
    assert top[0] > left[0] > right[0]
    assert top[0] == 255
    assert abs(left[0] - 0.81 * 255) < 6
    assert abs(right[0] - 0.62 * 255) < 6


def test_face_texture_without_hash(assets):
    picture = render_item(assets, "plain")
    assert picture is not None and picture.getpixel((32, 14))[3] == 255


def test_select_condition_and_composite(assets):
    assert render_item(assets, "picked").getpixel((32, 32)) == RED
    assert render_item(assets, "conditional").getpixel((32, 32)) == RED
    both = render_item(assets, "both")
    # The flat apple is drawn over the block
    assert both.getpixel((32, 32)) == RED


def test_missing_parts_give_no_picture(assets):
    assert render_item(assets, "no_texture") is None
    assert render_item(assets, "no_model") is None
    assert render_item(assets, "loop") is None
    assert render_item(assets, "broken") is None
    assert render_item(assets, "not_there") is None


def test_render_all(assets, tmp_path):
    seen = []
    count = render_all(assets, tmp_path, lambda done, total: seen.append(total))
    names = {path.name for path in tmp_path.iterdir()}
    assert count == 7
    assert "apple.png" in names and "both.png" in names
    assert "Bad Name.png" not in names and "broken.png" not in names
    # Sprites in the jar are kept as they are
    assert "_heart_full.png" in names
    assert Image.open(tmp_path / "_heart_full.png").size == (9, 9)
    assert seen


def test_status_and_paths(tmp_path):
    icons = ItemIcons(tmp_path)
    assert icons.status() == {"state": "none"}
    folder = tmp_path / "item_icons"
    folder.mkdir()
    (folder / "apple.png").write_bytes(_png(RED))
    (folder / "info.json").write_text(
        json.dumps({"version": "1.0", "count": 1, "made": "2026-01-01T00:00:00Z"})
    )
    assert icons.status() == {
        "state": "ready",
        "version": "1.0",
        "count": 1,
        "made": "2026-01-01T00:00:00Z",
    }
    assert icons.path("apple") == folder / "apple.png"
    assert icons.path("pear") is None
    for name in ("../item_icons/apple", "Apple", "", "info.json", "a" * 65):
        assert icons.path(name) is None
    assert ItemIcons.get(tmp_path) is ItemIcons.get(tmp_path)


def test_make_replaces_the_pictures(tmp_path):
    jar = tmp_path / "client.jar"
    _jar(jar)
    icons = ItemIcons(tmp_path / "config")
    old = tmp_path / "config" / "item_icons"
    old.mkdir(parents=True)
    (old / "gone.png").write_bytes(_png(RED))
    icons._make(jar, "9.9")  # pylint: disable=protected-access
    status = icons.status()
    assert status["state"] == "ready" and status["version"] == "9.9"
    assert status["count"] == 7
    assert icons.path("apple") and not icons.path("gone")
    assert not (tmp_path / "config" / "item_icons.new").exists()
    assert not (tmp_path / "config" / "item_icons.old").exists()


class _Response:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data

    def iter_content(self, _size):
        yield self.data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _session(jar_bytes, sha1):
    pages = {
        item_icons.MANIFEST: {
            "latest": {"release": "9.9"},
            "versions": [{"id": "9.9", "url": "https://example.invalid/9.9.json"}],
        },
        "https://example.invalid/9.9.json": {
            "downloads": {
                "client": {
                    "url": "https://example.invalid/client.jar",
                    "sha1": sha1,
                    "size": len(jar_bytes),
                }
            }
        },
        "https://example.invalid/client.jar": jar_bytes,
    }

    class Session:
        def get(self, url, **_kwargs):
            return _Response(pages[url])

    return Session


def test_download_checks_the_checksum(tmp_path, monkeypatch):
    jar_bytes = _jar().getvalue()
    icons = ItemIcons(tmp_path)
    good = hashlib.sha1(jar_bytes).hexdigest()
    monkeypatch.setattr(item_icons.requests, "Session", _session(jar_bytes, good))
    jar, version = icons._download(tmp_path)  # pylint: disable=protected-access
    assert version == "9.9" and jar.read_bytes() == jar_bytes

    monkeypatch.setattr(item_icons.requests, "Session", _session(jar_bytes, "0" * 40))
    with pytest.raises(ValueError):
        icons._download(tmp_path)  # pylint: disable=protected-access


def test_run_reports_errors(tmp_path, monkeypatch):
    icons = ItemIcons(tmp_path)
    jar_bytes = _jar().getvalue()
    monkeypatch.setattr(item_icons.requests, "Session", _session(jar_bytes, "0" * 40))
    icons._job = {"state": "working"}  # pylint: disable=protected-access
    icons._run()  # pylint: disable=protected-access
    status = icons.status()
    assert status["state"] == "error" and "checksum" in status["error"]


def test_run_makes_the_pictures(tmp_path, monkeypatch):
    icons = ItemIcons(tmp_path)
    jar_bytes = _jar().getvalue()
    good = hashlib.sha1(jar_bytes).hexdigest()
    monkeypatch.setattr(item_icons.requests, "Session", _session(jar_bytes, good))
    icons._run()  # pylint: disable=protected-access
    assert icons.status()["state"] == "ready"
    assert icons.path("apple") is not None
