import gzip
import json
import os
import zipfile

import pytest

from app.classes.helpers import player_data, world_tools
from app.classes.helpers.world_tools import (
    END,
    NETHER,
    OVERWORLD,
    WorldDownloads,
    WorldError,
)
from tests.classes.helpers.nbt_writer import byte, long, nbt_file

ALEX = "5f8a3c0e-1d2b-4c3d-8e4f-0a1b2c3d4e5f"
STEVE = "0b1c2d3e-4f50-4a6b-8c7d-9e0f1a2b3c4d"

NETHER_ID = "minecraft:the_nether"
DRAGON_FIGHT = {"DragonKilled": byte(1), "PreviouslyKilled": byte(1)}


def touch(path, data=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def make_server(tmp_path, layout="vanilla", level_dat=None, level_name=None):
    """A server folder with a world in one of the three layouts, each
    dimension holding one region file."""
    server = tmp_path / "server"
    world = server / (level_name or "world")
    if level_name:
        touch(server / "server.properties", f"level-name={level_name}\n".encode())
    touch(world / "level.dat", nbt_file(level_dat or {"Data": {"LevelName": "w"}}))
    touch(world / "session.lock")
    if layout == "vanilla":
        touch(world / "region" / "r.0.0.mca")
        touch(world / "DIM-1" / "region" / "r.0.0.mca")
        touch(world / "DIM1" / "region" / "r.0.0.mca")
    elif layout == "bukkit":
        touch(world / "region" / "r.0.0.mca")
        touch(server / "world_nether" / "DIM-1" / "region" / "r.0.0.mca")
        touch(server / "world_nether" / "level.dat", nbt_file({"Data": {}}))
        touch(server / "world_the_end" / "DIM1" / "region" / "r.0.0.mca")
    elif layout == "26":
        for dimension in (OVERWORLD, NETHER, END):
            folder = world / "dimensions" / "minecraft" / dimension
            touch(folder / "region" / "r.0.0.mca")
    return server, world


def nbt(path):
    return player_data.read_nbt(path)


# --------------------------------------------------------------------------
# Finding the world
# --------------------------------------------------------------------------


def test_dimension_folders_vanilla(tmp_path):
    _server, world = make_server(tmp_path)
    folders = world_tools.dimension_folders(world)
    assert folders == {
        OVERWORLD: [world / "region"],
        NETHER: [world / "DIM-1"],
        END: [world / "DIM1"],
    }


def test_dimension_folders_bukkit(tmp_path):
    server, world = make_server(tmp_path, "bukkit")
    folders = world_tools.dimension_folders(world)
    assert folders[NETHER] == [server / "world_nether" / "DIM-1"]
    assert folders[END] == [server / "world_the_end" / "DIM1"]


def test_dimension_folders_minecraft_26(tmp_path):
    _server, world = make_server(tmp_path, "26")
    new = world / "dimensions" / "minecraft"
    assert world_tools.dimension_folders(world) == {
        OVERWORLD: [new / OVERWORLD],
        NETHER: [new / NETHER],
        END: [new / END],
    }


def test_dimension_folders_skip_links_and_missing(tmp_path):
    _server, world = make_server(tmp_path, "bare")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    os.symlink(outside, world / "DIM-1")
    assert world_tools.dimension_folders(world) == {OVERWORLD: [], NETHER: [], END: []}


def test_java_world_must_be_inside_the_server(tmp_path):
    server, world = make_server(tmp_path)
    assert world_tools.java_world(server) == world.resolve()
    (server / "server.properties").write_text("level-name=.\n")
    assert world_tools.java_world(server) is None
    (server / "server.properties").write_text("level-name=../other\n")
    assert world_tools.java_world(server) is None


def test_world_roots(tmp_path):
    server, world = make_server(tmp_path, "bukkit")
    assert world_tools.world_roots(server, "minecraft-java") == [
        world,
        server / "world_nether",
        server / "world_the_end",
    ]
    assert not world_tools.world_roots(server, "steam_cmd")


def test_bedrock_world(tmp_path):
    server = tmp_path / "server"
    touch(server / "worlds" / "Bedrock level" / "level.dat")
    assert world_tools.world_roots(server, "minecraft-bedrock") == [
        server / "worlds" / "Bedrock level"
    ]
    touch(server / "server.properties", b"level-name=My World\n")
    assert not world_tools.world_roots(server, "minecraft-bedrock")
    touch(server / "worlds" / "My World" / "db" / "000001.ldb")
    assert world_tools.world_roots(server, "minecraft-bedrock") == [
        server / "worlds" / "My World"
    ]
    (server / "server.properties").write_text("level-name=../../x\n")
    assert world_tools.bedrock_world(server) is None


# --------------------------------------------------------------------------
# What the page shows
# --------------------------------------------------------------------------


def test_level_info_1_21(tmp_path):
    _server, world = make_server(
        tmp_path,
        level_dat={
            "Data": {
                "Version": {"Name": "1.21.4"},
                "WorldGenSettings": {"seed": long(-1234567890123)},
                "LastPlayed": long(1700000000123),
            }
        },
    )
    assert world_tools.level_info(world) == {
        "version": "1.21.4",
        "seed": "-1234567890123",
        "last_played": 1700000000,
    }


def test_level_info_old_seed(tmp_path):
    _server, world = make_server(tmp_path, level_dat={"Data": {"RandomSeed": long(42)}})
    assert world_tools.level_info(world) == {
        "version": None,
        "seed": "42",
        "last_played": None,
    }


def test_level_info_minecraft_26(tmp_path):
    _server, world = make_server(
        tmp_path, "26", level_dat={"Data": {"Version": {"Name": "26.3"}}}
    )
    touch(
        world / "data" / "minecraft" / "world_gen_settings.dat",
        nbt_file({"data": {"seed": long(7)}, "DataVersion": 4700}),
    )
    assert world_tools.level_info(world)["seed"] == "7"


def test_level_info_broken_level_dat(tmp_path):
    _server, world = make_server(tmp_path)
    (world / "level.dat").write_bytes(b"not nbt")
    assert world_tools.level_info(world) == {
        "version": None,
        "seed": None,
        "last_played": None,
    }


def test_overview_java(tmp_path):
    server, world = make_server(tmp_path)
    touch(world / "playerdata" / f"{ALEX}.dat", nbt_file({"Dimension": NETHER_ID}))
    touch(world / "playerdata" / f"{STEVE}.dat", nbt_file({"Dimension": 0}))
    (server / "usercache.json").write_text(
        json.dumps([{"uuid": ALEX, "name": "Alex", "expiresOn": "2030-01-01"}])
    )
    info = world_tools.overview(server, "minecraft-java")
    assert info["edition"] == "java"
    assert info["name"] == "world"
    assert info["folder"] == "world"
    assert info["folders"] == ["world"]
    assert info["exists"]
    assert info["size"] > 0
    dimensions = {d["id"]: d for d in info["dimensions"]}
    assert dimensions[NETHER]["players"] == ["Alex"]
    assert dimensions[NETHER]["folders"] == ["world/DIM-1"]
    assert dimensions[NETHER]["resettable"]
    assert dimensions[OVERWORLD]["players"] == [STEVE]
    assert not dimensions[OVERWORLD]["resettable"]


def test_overview_without_world(tmp_path):
    server = tmp_path / "server"
    server.mkdir()
    info = world_tools.overview(server, "minecraft-java")
    assert not info["exists"]
    assert info["dimensions"] is None
    assert world_tools.overview(server, "steam_cmd") is None


def test_overview_bedrock(tmp_path):
    server = tmp_path / "server"
    touch(server / "worlds" / "Bedrock level" / "db" / "CURRENT", b"MANIFEST")
    info = world_tools.overview(server, "minecraft-bedrock")
    assert info["edition"] == "bedrock"
    assert info["folder"] == "worlds/Bedrock level"
    assert info["size"] == len(b"MANIFEST")
    assert info["dimensions"] is None


# --------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------


def test_zip_world(tmp_path):
    server, world = make_server(tmp_path, "bukkit")
    touch(world / "datapacks" / "pack.json", b"{}" * 100)
    os.symlink(tmp_path, world / "link")
    target = tmp_path / "out.zip"
    roots = world_tools.world_roots(server, "minecraft-java")
    count = world_tools.zip_world(server, roots, target)
    with zipfile.ZipFile(target) as archive:
        infos = {info.filename: info for info in archive.infolist()}
    assert count == len(infos)
    assert set(infos) == {
        "world/level.dat",
        "world/region/r.0.0.mca",
        "world/datapacks/pack.json",
        "world_nether/level.dat",
        "world_nether/DIM-1/region/r.0.0.mca",
        "world_the_end/DIM1/region/r.0.0.mca",
    }
    assert infos["world/region/r.0.0.mca"].compress_type == zipfile.ZIP_STORED
    assert infos["world/level.dat"].compress_type == zipfile.ZIP_STORED
    assert infos["world/datapacks/pack.json"].compress_type == zipfile.ZIP_DEFLATED


def test_download_name():
    name = world_tools.download_name("My Server!", "../world")
    assert name.startswith("My-Server-world-")
    assert name.endswith(".zip")
    assert "/" not in name
    assert world_tools.download_name("***", "").startswith("world-world-")


def test_downloads_once_for_the_right_user(tmp_path):
    downloads = WorldDownloads()
    folder = tmp_path / "job"
    zip_path = touch(folder / "world.zip", b"zip")
    downloads.start("s1", 1, folder)
    assert downloads.status("s1", 1)["state"] == "zipping"
    assert downloads.status("s1", 2) is None
    downloads.finish("s1", 1, zip_path, 3, True)
    status = downloads.status("s1", "1")
    assert status["state"] == "ready"
    assert status["filename"] == "world.zip"
    assert status["size"] == 3
    assert status["files"] == 3
    assert status["saved"] is True
    assert "path" not in status and "folder" not in status
    token = status["token"]
    assert downloads.take(token, 2, "s1") is None
    assert downloads.take(token, 1, "s2") is None
    assert downloads.take("0" * 32, 1, "s1") is None
    assert downloads.take(token, 1, "s1") == zip_path
    assert downloads.take(token, 1, "s1") is None
    assert downloads.status("s1", 1) is None


def test_downloads_fail_and_replace(tmp_path):
    downloads = WorldDownloads()
    first = tmp_path / "first"
    first.mkdir()
    downloads.start("s1", 1, first)
    downloads.fail("s1", 1, "ZIP_FAILED", "disk full")
    assert not first.exists()
    status = downloads.status("s1", 1)
    assert (status["state"], status["error"], status["message"]) == (
        "failed",
        "ZIP_FAILED",
        "disk full",
    )
    second = tmp_path / "second"
    third = tmp_path / "third"
    second.mkdir()
    third.mkdir()
    downloads.start("s1", 1, second)
    downloads.start("s1", 1, third)
    assert not second.exists()
    # A zip finishing for a job that was replaced is thrown away
    late = touch(tmp_path / "late" / "world.zip")
    downloads.fail("s1", 1, "ZIP_FAILED", "x")
    downloads.finish("s1", 1, late, 1, None)
    assert not late.parent.exists()


def test_downloads_purge(tmp_path):
    downloads = WorldDownloads()
    ready = tmp_path / "ready"
    zipping = tmp_path / "zipping"
    downloads.start("s1", 1, ready)
    downloads.finish("s1", 1, touch(ready / "w.zip"), 1, None)
    downloads.start("s2", 1, zipping)
    zipping.mkdir()
    downloads.purge()
    assert ready.exists()
    downloads.purge(older_than=-1)
    assert not ready.exists()
    assert downloads.status("s1", 1) is None
    assert zipping.exists()
    assert downloads.status("s2", 1)["state"] == "zipping"


def test_one_world_tool_at_a_time():
    assert world_tools.begin("srv", "download") is None
    assert world_tools.busy("srv") == "download"
    assert world_tools.begin("srv", "reset") == "download"
    world_tools.end("srv")
    assert world_tools.busy("srv") is None
    assert world_tools.begin("srv", "reset") is None
    world_tools.end("srv")


# --------------------------------------------------------------------------
# Reset
# --------------------------------------------------------------------------


def test_remove_tag():
    raw = nbt_file({"Data": {"DragonFight": DRAGON_FIGHT, "Keep": 1}, "Other": "x"})
    smaller = player_data.remove_tag(raw, ("Data", "DragonFight"))
    assert player_data.parse_nbt(gzip.decompress(smaller)) == {
        "Data": {"Keep": 1},
        "Other": "x",
    }
    assert player_data.remove_tag(raw, ("Data", "Missing")) is None
    assert player_data.remove_tag(raw, ("Other", "DragonFight")) is None
    assert player_data.remove_tag(raw, ("Data", "Keep", "Deeper")) is None


def test_reset_nether_vanilla(tmp_path):
    server, world = make_server(tmp_path)
    result = world_tools.reset_dimension(server, NETHER)
    assert result == {"removed": ["world/DIM-1"], "dragon_reset": False}
    assert not (world / "DIM-1").exists()
    assert (world / "DIM1").exists()
    assert (world / "region").exists()


@pytest.mark.parametrize(
    "level_dat",
    [
        {"Data": {"DragonFight": DRAGON_FIGHT, "LevelName": "w"}},
        {"Data": {"DimensionData": {"1": {"DragonFight": DRAGON_FIGHT}}}},
    ],
    ids=["1.16-1.21", "1.9-1.15"],
)
def test_reset_end_forgets_the_dragon(tmp_path, level_dat):
    server, world = make_server(tmp_path, level_dat=level_dat)
    os.chmod(world / "level.dat", 0o640)
    result = world_tools.reset_dimension(server, END)
    assert result == {"removed": ["world/DIM1"], "dragon_reset": True}
    assert not (world / "DIM1").exists()
    assert (world / "DIM-1").exists()
    data = nbt(world / "level.dat")["Data"]
    assert "DragonFight" not in data
    assert "DragonFight" not in data.get("DimensionData", {}).get("1", {})
    assert (os.stat(world / "level.dat").st_mode & 0o777) == 0o640
    assert not (world / "level.dat.tmp").exists()


def test_reset_end_bukkit(tmp_path):
    server, _world = make_server(tmp_path, "bukkit")
    touch(
        server / "world_the_end" / "level.dat",
        nbt_file({"Data": {"DragonFight": DRAGON_FIGHT}}),
    )
    result = world_tools.reset_dimension(server, END)
    assert result == {"removed": ["world_the_end/DIM1"], "dragon_reset": True}
    assert "DragonFight" not in nbt(server / "world_the_end" / "level.dat")["Data"]
    # Only the dimension goes: Bukkit makes it again in the same folder
    assert (server / "world_the_end").is_dir()


def test_reset_end_minecraft_26(tmp_path):
    server, world = make_server(tmp_path, "26")
    before = (world / "level.dat").read_bytes()
    result = world_tools.reset_dimension(server, END)
    assert result == {
        "removed": ["world/dimensions/minecraft/the_end"],
        "dragon_reset": False,
    }
    assert (world / "level.dat").read_bytes() == before
    assert (world / "dimensions" / "minecraft" / NETHER).exists()


def test_reset_only_the_dragon(tmp_path):
    # The End was deleted by hand but the dragon record stayed
    server, world = make_server(
        tmp_path, "bare", level_dat={"Data": {"DragonFight": DRAGON_FIGHT}}
    )
    result = world_tools.reset_dimension(server, END)
    assert result == {"removed": [], "dragon_reset": True}
    assert "DragonFight" not in nbt(world / "level.dat")["Data"]


def test_reset_errors(tmp_path):
    server, world = make_server(tmp_path, "bare")
    with pytest.raises(WorldError) as error:
        world_tools.reset_dimension(server, OVERWORLD)
    assert error.value.code == "INVALID_DIMENSION"
    with pytest.raises(WorldError) as error:
        world_tools.reset_dimension(server, NETHER)
    assert error.value.code == "NOTHING_TO_RESET"
    with pytest.raises(WorldError) as error:
        world_tools.reset_dimension(tmp_path / "nothing", NETHER)
    assert error.value.code == "WORLD_NOT_FOUND"
    assert world.exists()


def test_reset_end_keeps_everything_if_level_dat_is_broken(tmp_path):
    server, world = make_server(tmp_path)
    (world / "level.dat").write_bytes(gzip.compress(b"\x0a\x00\x00\x0a\x00"))
    with pytest.raises(WorldError) as error:
        world_tools.reset_dimension(server, END)
    assert error.value.code == "LEVEL_DAT_ERROR"
    assert (world / "DIM1").exists()


def test_reset_refuses_folders_outside_the_server(tmp_path):
    server, world = make_server(tmp_path, "bare")
    outside = tmp_path / "outside_nether"
    touch(outside / "DIM-1" / "region" / "r.0.0.mca")
    os.symlink(outside, server / "world_nether")
    with pytest.raises(WorldError) as error:
        world_tools.reset_dimension(server, NETHER)
    assert error.value.code == "WORLD_NOT_FOUND"
    assert (outside / "DIM-1").exists()
    assert world.exists()
