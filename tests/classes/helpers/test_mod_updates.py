import json

import pytest

from app.classes.helpers import datapacks, mod_updates, modrinth

SERVER_ID = "s1"


def _root(tmp_path):
    (tmp_path / "app" / "config" / "db" / "servers" / SERVER_ID).mkdir(parents=True)
    return tmp_path


def _server(tmp_path, **extra):
    path = tmp_path / "server"
    path.mkdir(exist_ok=True)
    data = {
        "server_id": SERVER_ID,
        "type": "minecraft-java",
        "path": str(path),
        "executable": "server.jar",
        "execution_command": "java -jar server.jar nogui",
    }
    data.update(extra)
    return data


def _jar(name, update=None, enabled=True, project="p", title=None):
    return {
        "file": name,
        "enabled": enabled,
        "project_id": project,
        "title": title,
        "version": "1.0",
        "update": update,
    }


def test_outdated_counts_turned_on_files_with_an_update():
    items = [
        _jar("a.jar", "1.1", title="Alpha"),
        _jar("b.jar"),
        _jar("c.jar.disabled", "2.0", enabled=False),
        _jar("own.jar", "9", project=None),
    ]
    assert mod_updates.outdated(items) == [
        {
            "file": "a.jar",
            "title": "Alpha",
            "project_id": "p",
            "version": "1.0",
            "update": "1.1",
        }
    ]


def test_remember_keeps_mods_packs_and_choices(tmp_path):
    root = _root(tmp_path)
    assert not mod_updates.get(root, SERVER_ID)
    mod_updates.remember(
        root, SERVER_ID, "mods", [_jar("a.jar", "1.1")], platform="paper"
    )
    mod_updates.remember(root, SERVER_ID, "packs", [_jar("t.zip", "3", title="T")])
    state = mod_updates.get(root, SERVER_ID)
    assert state["platform"] == "paper"
    assert "game_version" not in state
    assert mod_updates.count(state) == 2
    assert mod_updates.names(state) == ["a.jar (1.0 → 1.1)", "T (1.0 → 3)"]
    # None clears a choice; nothing given keeps it
    mod_updates.remember(root, SERVER_ID, "mods", [], platform=None)
    state = mod_updates.get(root, SERVER_ID)
    assert state["platform"] is None
    assert mod_updates.count(state) == 1
    assert not list((root / "app" / "config" / "db" / "servers" / SERVER_ID).glob(".*"))


def test_nothing_is_saved_for_a_server_that_is_gone(tmp_path):
    mod_updates.remember(tmp_path, "gone", "mods", [_jar("a.jar", "1.1")])
    assert not (tmp_path / "app").exists()
    assert not mod_updates.get(tmp_path, "gone")


def test_a_damaged_file_reads_as_never_checked(tmp_path):
    root = _root(tmp_path)
    state = root / "app" / "config" / "db" / "servers" / SERVER_ID / "mod_updates.json"
    state.write_text("{not json")
    assert not mod_updates.get(root, SERVER_ID)
    state.write_text("[1, 2]")
    assert not mod_updates.get(root, SERVER_ID)


def test_a_choice_wins_over_what_is_found(tmp_path, monkeypatch):
    monkeypatch.setattr(modrinth, "detect_platform", lambda *args: "paper")
    monkeypatch.setattr(modrinth, "detect_game_version", lambda *args: "1.21.1")
    server = _server(tmp_path)
    assert mod_updates.target(server, "", {}) == ("paper", "1.21.1")
    chosen = {"platform": "fabric", "game_version": "1.20.4"}
    assert mod_updates.target(server, "", chosen) == ("fabric", "1.20.4")
    assert mod_updates.target(server, "", {"platform": "nonsense"}) == (
        None,
        "1.21.1",
    )


def _fake_check(monkeypatch, jars, packs, platform="fabric", version="1.21.1"):
    calls = []
    monkeypatch.setattr(modrinth, "detect_platform", lambda *args: platform)
    monkeypatch.setattr(modrinth, "detect_game_version", lambda *args: version)

    def fake_jars(_path, found_platform, game_version):
        calls.append(("mods", found_platform, game_version))
        return jars

    def fake_packs(_path, game_version):
        calls.append(("packs", game_version))
        return packs

    monkeypatch.setattr(modrinth, "installed", fake_jars)
    monkeypatch.setattr(datapacks, "installed", fake_packs)
    return calls


def test_check_asks_about_mods_and_data_packs(tmp_path, monkeypatch):
    root = _root(tmp_path)
    calls = _fake_check(
        monkeypatch, [_jar("a.jar", "1.1")], [_jar("t.zip", "3", project="t")]
    )
    state = mod_updates.check(root, _server(tmp_path), "")
    assert calls == [("mods", "fabric", "1.21.1"), ("packs", "1.21.1")]
    assert mod_updates.count(state) == 2
    assert state["mods_checked"] and state["packs_checked"]


@pytest.mark.parametrize(
    "platform, version, asked",
    [
        (None, "1.21.1", ["packs"]),  # vanilla: only data packs
        ("velocity", "1.21.1", ["mods"]),  # a proxy has no world
        ("paper", None, ["mods"]),  # no version: no data packs
    ],
)
def test_check_asks_only_what_fits(tmp_path, monkeypatch, platform, version, asked):
    root = _root(tmp_path)
    calls = _fake_check(monkeypatch, [], [], platform, version)
    mod_updates.check(root, _server(tmp_path), "")
    assert [call[0] for call in calls] == asked


def test_check_keeps_the_last_result_when_modrinth_fails(tmp_path, monkeypatch):
    root = _root(tmp_path)
    _fake_check(monkeypatch, [_jar("a.jar", "1.1")], [])
    mod_updates.check(root, _server(tmp_path), "")

    def offline(*args):
        raise modrinth.ModrinthError("MODRINTH_UNREACHABLE", "offline")

    monkeypatch.setattr(modrinth, "installed", offline)
    monkeypatch.setattr(datapacks, "installed", offline)
    state = mod_updates.check(root, _server(tmp_path), "")
    assert mod_updates.count(state) == 1


def test_update_all_installs_each_update(tmp_path, monkeypatch):
    root = _root(tmp_path)
    jars = [_jar("a.jar", "1.1", project="a"), _jar("b.jar", "2", project="b")]
    packs = [_jar("t.zip", "3", project="t")]
    _fake_check(monkeypatch, jars, packs)
    installs = []

    def fake_install(_path, platform, game_version, project_id, busy_key):
        installs.append((platform, game_version, project_id, busy_key))
        if project_id == "b":
            raise modrinth.ModrinthError("NO_COMPATIBLE_VERSION", "gone")
        return {"installed": [{"file": f"{project_id}-new.jar", "up_to_date": False}]}

    def fake_pack_install(_path, game_version, project_id, busy_key):
        installs.append(("pack", game_version, project_id, busy_key))
        return {"installed": [{"file": "t-3.zip", "up_to_date": False}]}

    monkeypatch.setattr(modrinth, "install", fake_install)
    monkeypatch.setattr(datapacks, "install", fake_pack_install)
    done = mod_updates.update_all(root, _server(tmp_path), "")
    assert installs == [
        ("fabric", "1.21.1", "a", SERVER_ID),
        ("fabric", "1.21.1", "b", SERVER_ID),
        ("pack", "1.21.1", "t", SERVER_ID),
    ]
    assert done == {"updated": ["a-new.jar", "t-3.zip"], "failed": ["b.jar: gone"]}


def test_update_all_without_updates_installs_nothing(tmp_path, monkeypatch):
    root = _root(tmp_path)
    _fake_check(monkeypatch, [_jar("a.jar")], [])
    monkeypatch.setattr(modrinth, "install", lambda *args: pytest.fail("installed"))
    assert mod_updates.update_all(root, _server(tmp_path), "") == {
        "updated": [],
        "failed": [],
    }


class _Servers:
    def __init__(self, servers):
        self.servers = servers

    def get_all_defined_servers(self):
        return self.servers

    @staticmethod
    def get_server_stats_by_id(server_id):
        if server_id == "broken":
            raise ValueError("no such server")
        return {"version": "Paper 1.21.1"}


class _Controller:
    def __init__(self, servers):
        self.servers = _Servers(servers)


def test_check_all_checks_java_servers_and_goes_on_after_trouble(tmp_path, monkeypatch):
    monkeypatch.setattr(mod_updates, "PAUSE_SECONDS", 0)
    checked = []
    monkeypatch.setattr(
        mod_updates,
        "check",
        lambda root, server, version: checked.append((server["server_id"], version)),
    )
    servers = [
        {"server_id": "broken", "type": "minecraft-java"},
        {"server_id": "bedrock", "type": "minecraft-bedrock"},
        {"server_id": "java", "type": "minecraft-java"},
    ]
    mod_updates.check_all(_Controller(servers), tmp_path)
    assert checked == [("java", "Paper 1.21.1")]


def test_the_state_file_is_plain_json(tmp_path):
    root = _root(tmp_path)
    mod_updates.remember(root, SERVER_ID, "mods", [_jar("a.jar", "1.1")])
    path = root / "app" / "config" / "db" / "servers" / SERVER_ID / "mod_updates.json"
    assert json.loads(path.read_text())["mods"][0]["file"] == "a.jar"
