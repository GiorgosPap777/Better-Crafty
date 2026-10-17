import json
import os
import struct

import pytest

from app.classes.helpers import player_data
from app.classes.helpers.player_data import (
    NbtError,
    has_player,
    list_players,
    normalise_stats,
    parse_item,
    parse_nbt,
    player_details,
    player_from_nbt,
    world_folder,
)
from tests.classes.helpers.nbt_writer import (
    byte,
    flt,
    int_array,
    long,
    nbt_file,
    short,
)

ALEX = "5f8a3c0e-1d2b-4c3d-8e4f-0a1b2c3d4e5f"
STEVE = "0b1c2d3e-4f50-4a6b-8c7d-9e0f1a2b3c4d"


MODERN_PLAYER = {
    "DataVersion": 4325,
    "Health": flt(14.0),
    "foodLevel": 18,
    "foodSaturationLevel": flt(2.5),
    "XpLevel": 30,
    "XpP": flt(0.5),
    "playerGameType": 1,
    "Dimension": "minecraft:the_nether",
    "Pos": [12.345, 64.0, -7.25],
    "SelectedItemSlot": 3,
    "attributes": [{"id": "minecraft:max_health", "base": 40.0}],
    "respawn": {"dimension": "minecraft:overworld", "pos": int_array([1, 70, 2])},
    "LastDeathLocation": {
        "dimension": "minecraft:the_end",
        "pos": int_array([100, 50, -100]),
    },
    "Inventory": [
        {
            "Slot": byte(3),
            "id": "minecraft:diamond_sword",
            "count": 1,
            "components": {
                "minecraft:enchantments": {"minecraft:sharpness": 5},
                "minecraft:damage": 120,
                "minecraft:custom_name": {"text": "Slicer", "extra": [" II"]},
            },
        },
        {
            "Slot": byte(20),
            "id": "minecraft:shulker_box",
            "count": 1,
            "components": {
                "minecraft:container": [
                    {"slot": 0, "item": {"id": "minecraft:dirt", "count": 64}},
                    {"slot": 1, "item": {"id": "minecraft:air", "count": 1}},
                ]
            },
        },
        {"Slot": byte(36), "id": "minecraft:stone", "count": 1},
    ],
    "equipment": {
        "head": {"id": "minecraft:netherite_helmet", "count": 1},
        "offhand": {"id": "minecraft:totem_of_undying", "count": 1},
        "body": {"id": "minecraft:saddle", "count": 1},
    },
    "EnderItems": [{"Slot": byte(5), "id": "minecraft:elytra", "count": 1}],
}

OLD_PLAYER = {
    "Health": flt(20.0),
    "playerGameType": 0,
    "Dimension": -1,
    "Pos": [0.0, 80.0, 0.0],
    "SpawnX": 10,
    "SpawnY": 64,
    "SpawnZ": -10,
    "Attributes": [{"Name": "minecraft:generic.max_health", "Base": 20.0}],
    "Inventory": [
        {
            "Slot": byte(0),
            "id": "minecraft:iron_sword",
            "Count": byte(1),
            "tag": {
                "Damage": 3,
                "display": {"Name": '{"text":"Old Blade"}'},
                "Enchantments": [{"id": "minecraft:smite", "lvl": short(2)}],
            },
        },
        {
            "Slot": byte(103),
            "id": "minecraft:diamond_helmet",
            "Count": byte(1),
            "tag": {"ench": [{"id": short(0), "lvl": short(4)}]},
        },
        {"Slot": byte(-106), "id": "minecraft:shield", "Count": byte(1)},
        {"Slot": byte(1), "id": "minecraft:cobblestone", "Count": byte(64)},
    ],
}


def write_server(tmp_path, players, level_name=None):
    server = tmp_path / "server"
    world = server / (level_name or "world")
    for folder in ("playerdata", "stats", "advancements"):
        (world / folder).mkdir(parents=True)
    if level_name:
        (server / "server.properties").write_text(f"level-name={level_name}\n")
    cache = []
    for uuid, (name, nbt) in players.items():
        (world / "playerdata" / f"{uuid}.dat").write_bytes(nbt_file(nbt))
        cache.append({"uuid": uuid, "name": name, "expiresOn": "2030-01-01"})
    (server / "usercache.json").write_text(json.dumps(cache))
    return server, world


def test_modern_player():
    player = player_from_nbt(parse_nbt(nbt_file(MODERN_PLAYER)))
    profile = player["profile"]
    assert profile["health"] == 14.0
    assert profile["max_health"] == 40.0
    assert profile["food"] == 18
    assert profile["xp_level"] == 30
    assert profile["game_mode"] == "creative"
    assert profile["dimension"] == "minecraft:the_nether"
    assert profile["position"] == [12.3, 64.0, -7.2]
    assert profile["selected_slot"] == 3
    assert profile["spawn"] == {
        "dimension": "minecraft:overworld",
        "position": [1, 70, 2],
    }
    assert profile["last_death"] == {
        "dimension": "minecraft:the_end",
        "position": [100, 50, -100],
    }

    slots = {entry["slot"]: entry["item"] for entry in player["inventory"]}
    assert set(slots) == {3, 20}
    assert slots[3] == {
        "id": "minecraft:diamond_sword",
        "count": 1,
        "name": "Slicer II",
        "enchantments": [["minecraft:sharpness", 5]],
        "damage": 120,
    }
    assert slots[20]["contents"] == [{"id": "minecraft:dirt", "count": 64, "slot": 0}]
    assert set(player["equipment"]) == {"head", "offhand"}
    assert player["ender_chest"] == [
        {"slot": 5, "item": {"id": "minecraft:elytra", "count": 1}}
    ]


def test_old_player():
    player = player_from_nbt(parse_nbt(nbt_file(OLD_PLAYER)))
    profile = player["profile"]
    assert profile["game_mode"] == "survival"
    assert profile["dimension"] == "minecraft:the_nether"
    assert profile["max_health"] == 20.0
    assert profile["spawn"] == {
        "dimension": "minecraft:overworld",
        "position": [10, 64, -10],
    }
    slots = {entry["slot"]: entry["item"] for entry in player["inventory"]}
    assert set(slots) == {0, 1}
    assert slots[0]["name"] == "Old Blade"
    assert slots[0]["damage"] == 3
    assert slots[0]["enchantments"] == [["minecraft:smite", 2]]
    assert slots[1]["count"] == 64
    assert player["equipment"]["head"]["enchantments"] == [["#0", 4]]
    assert player["equipment"]["offhand"]["id"] == "minecraft:shield"


def test_wrapped_enchantments_and_stored_enchantments():
    item = parse_item(
        {
            "id": "minecraft:enchanted_book",
            "count": 1,
            "components": {
                "minecraft:stored_enchantments": {
                    "levels": {"minecraft:mending": 1},
                    "show_in_tooltip": True,
                },
                "minecraft:potion_contents": {"potion": "minecraft:swiftness"},
                "minecraft:unbreakable": {},
            },
        }
    )
    assert item["enchantments"] == [["minecraft:mending", 1]]
    assert item["potion"] == "minecraft:swiftness"
    assert item["unbreakable"] is True


def test_empty_and_odd_items():
    assert parse_item(None) is None
    assert parse_item({"id": "minecraft:air"}) is None
    assert parse_item({"id": 5}) is None
    assert parse_item({"id": "mod:thing", "count": "x"}) == {
        "id": "mod:thing",
        "count": 1,
    }


def test_uncompressed_nbt():
    assert parse_nbt(nbt_file({"a": [1, 2], "b": long(5)}, compress=False)) == {
        "a": [1, 2],
        "b": 5,
    }


def test_modified_utf8():
    # Java writes NUL as C0 80 and an emoji as two encoded UTF-16 halves
    encoded = b"x\xc0\x80\xed\xa0\xbd\xed\xb8\x80"
    raw = b"\x0a\x00\x00\x08\x00\x01a" + struct.pack(">H", len(encoded)) + encoded
    assert parse_nbt(raw + b"\x00") == {"a": "x\x00\U0001f600"}


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"\x08\x00\x00",
        b"\x0a\x00\x00\x03\x00\x01a\x00",
        b"\x0a\x00\x00\x09\x00\x01a\x00\x00\x00\x00\x05\x00",
        b"\x0a\x00\x00\x0d\x00\x01a\x00",
        b"\x1f\x8bnot gzip",
    ],
)
def test_bad_nbt(raw):
    with pytest.raises(NbtError):
        parse_nbt(raw)


def test_nbt_depth_limit():
    nested = {}
    for _ in range(player_data.MAX_DEPTH + 5):
        nested = {"n": nested}
    with pytest.raises(NbtError):
        parse_nbt(nbt_file(nested))


def test_nbt_size_limit(monkeypatch):
    monkeypatch.setattr(player_data, "MAX_NBT_BYTES", 1000)
    with pytest.raises(NbtError):
        parse_nbt(nbt_file({"big": "x" * 5000}))


def test_modern_stats():
    stats = normalise_stats(
        {
            "stats": {
                "minecraft:custom": {"minecraft:play_time": 72000, "minecraft:jump": 3},
                "minecraft:mined": {"minecraft:stone": 10, "bad": "x"},
            },
            "DataVersion": 4325,
        }
    )
    assert stats == {
        "minecraft:custom": {"minecraft:play_time": 72000, "minecraft:jump": 3},
        "minecraft:mined": {"minecraft:stone": 10},
    }


def test_play_one_minute_is_play_time():
    stats = normalise_stats(
        {"stats": {"minecraft:custom": {"minecraft:play_one_minute": 200}}}
    )
    assert stats["minecraft:custom"]["minecraft:play_time"] == 200


def test_1_12_stats():
    stats = normalise_stats(
        {
            "stat.playOneMinute": 400,
            "stat.walkOneCm": 1000,
            "stat.mineBlock.minecraft.stone": 7,
            "stat.killEntity.Zombie": 2,
            "achievement.openInventory": 1,
        }
    )
    assert stats == {
        "minecraft:custom": {
            "minecraft:play_one_minute": 400,
            "minecraft:play_time": 400,
            "minecraft:walk_one_cm": 1000,
        },
        "minecraft:mined": {"minecraft:stone": 7},
        "minecraft:killed": {"Zombie": 2},
    }


def test_list_players(tmp_path):
    server, world = write_server(
        tmp_path, {ALEX: ("Alex", MODERN_PLAYER), STEVE: ("Steve", OLD_PLAYER)}
    )
    (world / "stats" / f"{ALEX}.json").write_text(
        json.dumps({"stats": {"minecraft:custom": {"minecraft:play_time": 999}}})
    )
    (world / "playerdata" / "notes.dat").write_bytes(b"x")
    (world / "playerdata" / f"{STEVE}.dat_old").write_bytes(b"x")
    os.utime(world / "playerdata" / f"{ALEX}.dat", (1000, 1000))
    os.utime(world / "playerdata" / f"{STEVE}.dat", (2000, 2000))

    assert list_players(server) == [
        {"uuid": STEVE, "name": "Steve", "last_played": 2000, "play_time": None},
        {"uuid": ALEX, "name": "Alex", "last_played": 1000, "play_time": 999},
    ]


def test_players_folder_of_minecraft_26(tmp_path):
    server, world = write_server(tmp_path, {})
    for folder in ("data", "stats", "advancements"):
        (world / "players" / folder).mkdir(parents=True)
    (world / "players" / "data" / f"{ALEX}.dat").write_bytes(nbt_file(MODERN_PLAYER))
    (world / "players" / "stats" / f"{ALEX}.json").write_text(
        json.dumps({"stats": {"minecraft:custom": {"minecraft:play_time": 42}}})
    )
    # Left over from before the world was converted: not read any more
    (world / "playerdata" / f"{STEVE}.dat").write_bytes(nbt_file(OLD_PLAYER))

    assert [(p["uuid"], p["play_time"]) for p in list_players(server)] == [(ALEX, 42)]
    assert has_player(server, ALEX)
    assert not has_player(server, STEVE)
    details = player_details(server, ALEX)
    assert details["profile"]["dimension"] == "minecraft:the_nether"
    assert details["stats"]["minecraft:custom"]["minecraft:play_time"] == 42


def test_list_players_without_world(tmp_path):
    assert list_players(tmp_path) == []


def test_has_player(tmp_path):
    server, world = write_server(tmp_path, {ALEX: ("Alex", MODERN_PLAYER)})
    (world / "stats" / f"{STEVE}.json").write_text("{}")
    assert has_player(server, ALEX)
    assert has_player(server, STEVE.upper())
    assert not has_player(server, "00000000-0000-4000-8000-000000000000")
    assert not has_player(server, "../" + ALEX)
    assert not has_player(tmp_path / "nowhere", ALEX)


def test_world_folder(tmp_path):
    (tmp_path / "server.properties").write_text("level-name=my\\u0020world\n")
    assert world_folder(tmp_path) == (tmp_path / "my world").resolve()
    (tmp_path / "server.properties").write_text("level-name=../elsewhere\n")
    assert world_folder(tmp_path) is None
    (tmp_path / "server.properties").write_text("level-name=/etc\n")
    assert world_folder(tmp_path) is None
    (tmp_path / "server.properties").unlink()
    assert world_folder(tmp_path) == (tmp_path / "world").resolve()


def test_player_details(tmp_path):
    server, world = write_server(tmp_path, {ALEX: ("Alex", MODERN_PLAYER)})
    (world / "advancements" / f"{ALEX}.json").write_text(
        json.dumps(
            {
                "minecraft:story/mine_stone": {
                    "criteria": {"get_stone": "2026-01-01 10:00:00 +0000"},
                    "done": True,
                },
                "minecraft:story/smelt_iron": {
                    "criteria": {"iron": "2026-02-01 10:00:00 +0000"},
                    "done": True,
                },
                "minecraft:story/enter_the_end": {"criteria": {}, "done": False},
                "minecraft:recipes/misc/stick": {
                    "criteria": {"x": "2026-03-01 10:00:00 +0000"},
                    "done": True,
                },
                "DataVersion": 4325,
            }
        )
    )
    details = player_details(server, ALEX.upper())
    assert details["name"] == "Alex"
    assert details["profile"]["game_mode"] == "creative"
    assert details["stats"] is None
    assert [adv["id"] for adv in details["advancements"]] == [
        "minecraft:story/smelt_iron",
        "minecraft:story/mine_stone",
    ]
    assert details["playerdata_error"] is False


def test_player_details_broken_file(tmp_path):
    server, world = write_server(tmp_path, {})
    (world / "playerdata" / f"{ALEX}.dat").write_bytes(b"\x1f\x8bbroken")
    (world / "stats" / f"{ALEX}.json").write_text('{"stats": {}}')
    details = player_details(server, ALEX)
    assert details["playerdata_error"] is True
    assert details["inventory"] is None


def test_player_details_unknown_and_invalid(tmp_path):
    server, _ = write_server(tmp_path, {})
    assert player_details(server, ALEX) is None
    with pytest.raises(ValueError):
        player_details(server, "../../etc/passwd")
