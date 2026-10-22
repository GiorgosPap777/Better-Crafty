import hashlib
import json

import pytest

from app.classes.helpers import modrinth


def test_platform_from_the_jar_name_and_command(tmp_path):
    assert modrinth.detect_platform(tmp_path, "paper-1.21.4-232.jar") == "paper"
    assert modrinth.detect_platform(tmp_path, "purpur-1.21.4.jar") == "purpur"
    assert modrinth.detect_platform(tmp_path, "craftbukkit.jar") == "bukkit"
    command = (
        "java -Xmx4G @libraries/net/neoforged/neoforge/21.1.77/unix_args.txt nogui"
    )
    assert modrinth.detect_platform(tmp_path, "", command) == "neoforge"
    command = "java @libraries/net/minecraftforge/forge/1.20.1-47.2.0/unix_args.txt"
    assert modrinth.detect_platform(tmp_path, "", command) == "forge"


def test_platform_from_the_files(tmp_path):
    assert modrinth.detect_platform(tmp_path, "server.jar") is None
    (tmp_path / "bukkit.yml").write_text("")
    assert modrinth.detect_platform(tmp_path, "server.jar") == "bukkit"
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "paper-global.yml").write_text("")
    assert modrinth.detect_platform(tmp_path, "server.jar") == "paper"
    (tmp_path / ".fabric").mkdir()
    assert modrinth.detect_platform(tmp_path, "server.jar") == "fabric"


def test_paper_with_neoforged_tools_is_paper(tmp_path):
    # A real Paper 1.21.4 keeps NeoForged's remapping tools in libraries/
    (tmp_path / "libraries" / "net" / "neoforged" / "AutoRenamingTool").mkdir(
        parents=True
    )
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "paper-global.yml").write_text("")
    (tmp_path / "bukkit.yml").write_text("")
    assert modrinth.detect_platform(tmp_path, "server.jar") == "paper"
    (tmp_path / "libraries" / "net" / "neoforged" / "neoforge").mkdir()
    assert modrinth.detect_platform(tmp_path, "server.jar") == "neoforge"


@pytest.mark.parametrize(
    "stats, executable, command, expected",
    [
        ("Paper 1.21.4", "", "", "1.21.4"),
        ("1.20.1", "", "", "1.20.1"),
        ("26.1", "", "", "26.1"),
        ("", "minecraft_server.1.21.4.jar", "", "1.21.4"),
        ("", "fabric-server-mc.1.21.4-loader.0.16.10-launcher.1.0.1.jar", "", "1.21.4"),
        ("", "", "java @libraries/net/minecraftforge/forge/1.20.1-47.2.0/x", "1.20.1"),
        (
            "",
            "",
            "java @libraries/net/neoforged/neoforge/21.1.77/unix_args.txt",
            "1.21.1",
        ),
        (
            "",
            "",
            "java @libraries/net/neoforged/neoforge/20.4.237/unix_args.txt",
            "1.20.4",
        ),
        ("Velocity 3.4.0", "velocity.jar", "", None),
        ("", "server.jar", "java -jar server.jar nogui", None),
    ],
)
def test_game_version(tmp_path, stats, executable, command, expected):
    assert (
        modrinth.detect_game_version(tmp_path, stats, executable, command) == expected
    )


def test_game_version_from_paper_history(tmp_path):
    (tmp_path / "version_history.json").write_text(
        json.dumps({"currentVersion": "git-Paper-232 (MC: 1.21.4)"})
    )
    assert modrinth.detect_game_version(tmp_path, "Paper 1.21.3") == "1.21.4"


def test_platform_info():
    assert modrinth.platform_info(None, "1.21.4") == {"supported": False}
    info = modrinth.platform_info("fabric", "1.21.4")
    assert info["folder"] == "mods" and info["kind"] == "mod"
    assert info["game_version"] == "1.21.4"
    proxy = modrinth.platform_info("velocity", "3.4.0")
    assert proxy["folder"] == "plugins" and proxy["game_version"] is None
    assert not proxy["needs_game_version"]


def test_search_facets():
    assert modrinth.search_facets("paper", "1.21.4") == [
        ["categories:paper", "categories:spigot", "categories:bukkit"],
        ["project_type:plugin"],
        ["versions:1.21.4"],
    ]
    assert modrinth.search_facets("fabric", None) == [
        ["categories:fabric"],
        ["project_type:mod"],
        ["server_side!=unsupported"],
    ]
    assert ["versions:1.21.4"] not in modrinth.search_facets("velocity", "1.21.4")


def test_pick_version_prefers_releases_and_the_best_loader():
    versions = [
        {"id": "a", "version_type": "beta", "loaders": ["paper"]},
        {"id": "b", "version_type": "release", "loaders": ["bukkit"]},
        {"id": "c", "version_type": "release", "loaders": ["paper"]},
    ]
    assert modrinth.pick_version(versions, ["paper", "spigot", "bukkit"])["id"] == "c"
    assert modrinth.pick_version(versions[:1], ["paper"])["id"] == "a"
    assert modrinth.pick_version(versions, ["fabric"]) is None


@pytest.mark.parametrize(
    "name, ok",
    [
        ("LuckPerms-Bukkit-5.5.71.jar", True),
        ("fabric-api-0.119.4+1.21.4.jar", True),
        ("../evil.jar", False),
        ("sub/evil.jar", False),
        ("..\\evil.jar", False),
        (".hidden.jar", False),
        ("readme.txt", False),
        ("C:evil.jar", False),
        ("", False),
        (None, False),
    ],
)
def test_safe_jar_name(name, ok):
    assert modrinth.safe_jar_name(name) is ok


def _version(project, version_id, data, deps=(), url=None):
    return {
        "id": version_id,
        "project_id": project,
        "version_number": version_id,
        "version_type": "release",
        "loaders": ["fabric"],
        "dependencies": [
            {"project_id": dep, "dependency_type": "required"} for dep in deps
        ],
        "files": [
            {
                "primary": True,
                "url": url
                or f"https://cdn.modrinth.com/data/{project}/{version_id}.jar",
                "filename": f"{project}-{version_id}.jar",
                "size": len(data),
                "hashes": {"sha512": hashlib.sha512(data).hexdigest()},
            }
        ],
    }


def test_primary_file_must_come_from_modrinth():
    version = _version("abc", "1", b"x", url="https://example.com/abc.jar")
    with pytest.raises(modrinth.ModrinthError) as ex:
        modrinth.primary_file(version)
    assert ex.value.code == "BAD_FILE"
    version = _version("abc", "1", b"x", url="http://cdn.modrinth.com/abc.jar")
    with pytest.raises(modrinth.ModrinthError):
        modrinth.primary_file(version)
    assert modrinth.primary_file(_version("abc", "1", b"x"))["filename"] == "abc-1.jar"


class _Response:
    def __init__(self, data: bytes):
        self.status_code = 200
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, _size):
        yield self.data


def _fake_modrinth(monkeypatch, versions, files, known=None):
    """Answer the helper's calls to Modrinth from these dicts."""

    def fake_get(url, **_params):
        project = url.split("/project/")[1].split("/")[0]
        return [versions[project]]

    monkeypatch.setattr(modrinth, "_get", fake_get)
    monkeypatch.setattr(
        modrinth, "installed", lambda *args: list((known or {}).values())
    )
    monkeypatch.setattr(
        modrinth.requests,
        "get",
        lambda url, **kwargs: _Response(files[url.rsplit("/", 1)[1]]),
    )


def test_install_with_dependencies(tmp_path, monkeypatch):
    versions = {
        "chunky": _version("chunky", "1.4", b"chunky", deps=["fabric-api"]),
        "fabric-api": _version("fabric-api", "0.119", b"api"),
    }
    files = {"1.4.jar": b"chunky", "0.119.jar": b"api"}
    _fake_modrinth(monkeypatch, versions, files)
    result = modrinth.install(tmp_path, "fabric", "1.21.4", "chunky", "s1")
    assert [item["file"] for item in result["installed"]] == [
        "chunky-1.4.jar",
        "fabric-api-0.119.jar",
    ]
    assert (tmp_path / "mods" / "chunky-1.4.jar").read_bytes() == b"chunky"
    assert (tmp_path / "mods" / "fabric-api-0.119.jar").read_bytes() == b"api"
    assert sorted(p.name for p in (tmp_path / "mods").iterdir()) == [
        "chunky-1.4.jar",
        "fabric-api-0.119.jar",
    ]


def test_install_replaces_the_old_file_and_skips_present_dependencies(
    tmp_path, monkeypatch
):
    mods = tmp_path / "mods"
    mods.mkdir()
    (mods / "chunky-1.3.jar").write_bytes(b"old")
    (mods / "fabric-api-0.100.jar").write_bytes(b"old api")
    known = {
        "chunky": {
            "project_id": "chunky",
            "file": "chunky-1.3.jar",
            "version_id": "1.3",
        },
        "fabric-api": {
            "project_id": "fabric-api",
            "file": "fabric-api-0.100.jar",
            "version_id": "0.100",
        },
    }
    versions = {
        "chunky": _version("chunky", "1.4", b"chunky", deps=["fabric-api"]),
        "fabric-api": _version("fabric-api", "0.119", b"api"),
    }
    _fake_modrinth(monkeypatch, versions, {"1.4.jar": b"chunky"}, known)
    result = modrinth.install(tmp_path, "fabric", "1.21.4", "chunky", "s1")
    assert result["installed"] == [
        {
            "project_id": "chunky",
            "file": "chunky-1.4.jar",
            "version": "1.4",
            "replaced": "chunky-1.3.jar",
            "up_to_date": False,
        }
    ]
    assert sorted(p.name for p in mods.iterdir()) == [
        "chunky-1.4.jar",
        "fabric-api-0.100.jar",
    ]


def test_install_refuses_a_damaged_download(tmp_path, monkeypatch):
    versions = {"chunky": _version("chunky", "1.4", b"chunky")}
    _fake_modrinth(monkeypatch, versions, {"1.4.jar": b"something else"})
    with pytest.raises(modrinth.ModrinthError) as ex:
        modrinth.install(tmp_path, "fabric", "1.21.4", "chunky", "s1")
    assert ex.value.code == "BAD_CHECKSUM"
    assert not list((tmp_path / "mods").iterdir())


def test_one_install_at_a_time(tmp_path, monkeypatch):
    _fake_modrinth(monkeypatch, {}, {})
    modrinth._busy.add("s1")  # pylint: disable=protected-access
    try:
        with pytest.raises(modrinth.ModrinthError) as ex:
            modrinth.install(tmp_path, "fabric", "1.21.4", "chunky", "s1")
        assert ex.value.code == "BUSY"
    finally:
        modrinth._busy.discard("s1")  # pylint: disable=protected-access


def test_turn_a_jar_off_on_and_remove_it(tmp_path):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / "a.jar").write_bytes(b"a")
    (plugins / "notes.txt").write_text("")
    (plugins / "folder.jar").mkdir()
    jars = modrinth.local_jars(tmp_path, "paper")
    assert [(jar["file"], jar["enabled"]) for jar in jars] == [("a.jar", True)]
    assert modrinth.change_jar(tmp_path, "paper", "a.jar", "disable") == (
        "a.jar.disabled"
    )
    assert (plugins / "a.jar.disabled").is_file()
    assert modrinth.change_jar(tmp_path, "paper", "a.jar.disabled", "disable") == (
        "a.jar.disabled"
    )
    assert modrinth.change_jar(tmp_path, "paper", "a.jar.disabled", "enable") == (
        "a.jar"
    )
    assert modrinth.change_jar(tmp_path, "paper", "a.jar", "remove") is None
    assert sorted(p.name for p in plugins.iterdir()) == ["folder.jar", "notes.txt"]


@pytest.mark.parametrize(
    "name, action, code",
    [
        ("a.jar", "delete", "INVALID_ACTION"),
        ("../server.properties", "remove", "FILE_NOT_FOUND"),
        ("notes.txt", "remove", "FILE_NOT_FOUND"),
        ("folder.jar", "remove", "FILE_NOT_FOUND"),
        ("b.jar", "disable", "FILE_EXISTS"),
    ],
)
def test_change_jar_refuses(tmp_path, name, action, code):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (tmp_path / "server.properties").write_text("")
    (plugins / "a.jar").write_bytes(b"a")
    (plugins / "b.jar").write_bytes(b"b")
    (plugins / "b.jar.disabled").write_bytes(b"old b")
    (plugins / "notes.txt").write_text("")
    (plugins / "folder.jar").mkdir()
    with pytest.raises(modrinth.ModrinthError) as ex:
        modrinth.change_jar(tmp_path, "paper", name, action)
    assert ex.value.code == code
    assert (tmp_path / "server.properties").exists()
