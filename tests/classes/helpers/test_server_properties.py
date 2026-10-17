import pytest

from app.classes.helpers.server_properties import (
    read_settings,
    validate_changes,
    write_changes,
)

JAVA_FILE = (
    "#Minecraft server properties\r\n"
    "#Tue Oct 15 07:38:41 UTC 2026\r\n"
    "difficulty=easy\r\n"
    "gamemode=survival\r\n"
    "max-players=20\r\n"
    "motd=\\u00A7aHello \\\\u0041 there\r\n"
    "pvp=true\r\n"
    "custom-key=keep me\r\n"
    "level-seed=\r\n"
)


@pytest.fixture(name="java_props")
def java_props_fixture(tmp_path):
    path = tmp_path / "server.properties"
    path.write_bytes(JAVA_FILE.encode())
    return path


def by_key(settings):
    return {s["key"]: s for s in settings}


def test_read_only_known_keys_present_in_file(java_props):
    settings = by_key(read_settings(java_props, "minecraft-java"))
    assert set(settings) == {
        "difficulty",
        "gamemode",
        "max-players",
        "motd",
        "pvp",
        "level-seed",
    }
    assert settings["pvp"]["value"] is True
    assert settings["max-players"]["value"] == 20
    assert settings["difficulty"]["options"] == ["peaceful", "easy", "normal", "hard"]


def test_read_decodes_unicode_escapes_but_not_escaped_backslash(java_props):
    settings = by_key(read_settings(java_props, "minecraft-java"))
    assert settings["motd"]["value"] == "§aHello \\\\u0041 there"


def test_write_keeps_other_lines_and_line_endings(java_props):
    changes = validate_changes(
        {"difficulty": "hard", "pvp": False, "max-players": 50}, "minecraft-java"
    )
    write_changes(java_props, changes)
    text = java_props.read_bytes().decode()
    assert text == (
        JAVA_FILE.replace("difficulty=easy", "difficulty=hard")
        .replace("pvp=true", "pvp=false")
        .replace("max-players=20", "max-players=50")
    )


def test_trailing_backslash_does_not_swallow_the_next_line(java_props):
    changes = validate_changes({"motd": "path C:\\"}, "minecraft-java")
    assert changes["motd"] == "path C:\\\\"
    assert validate_changes({"motd": "a\\\\"}, "minecraft-java")["motd"] == "a\\\\"
    write_changes(java_props, changes)
    assert "\\\\\r\npvp=true\r\n" in java_props.read_bytes().decode()


def test_write_replaces_the_file_in_one_step(java_props, tmp_path):
    java_props.chmod(0o640)
    link = tmp_path / "link.properties"
    link.symlink_to(java_props)
    write_changes(link, validate_changes({"pvp": False}, "minecraft-java"))
    assert link.is_symlink()
    assert "pvp=false" in java_props.read_text(encoding="utf-8")
    assert java_props.stat().st_mode & 0o777 == 0o640
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "link.properties",
        "server.properties",
    ]


def test_motd_round_trip_with_non_ascii(java_props):
    changes = validate_changes({"motd": "§bΓεια σου\nline two"}, "minecraft-java")
    assert changes["motd"] == (
        "\\u00a7b\\u0393\\u03b5\\u03b9\\u03b1 \\u03c3\\u03bf\\u03c5\\nline two"
    )
    write_changes(java_props, changes)
    settings = by_key(read_settings(java_props, "minecraft-java"))
    assert settings["motd"]["value"] == "§bΓεια σου\\nline two"


def test_bedrock_text_written_as_utf8(tmp_path):
    path = tmp_path / "server.properties"
    path.write_text("server-name=Dedicated Server\nallow-list=false\n")
    changes = validate_changes({"server-name": "Γεια"}, "minecraft-bedrock")
    write_changes(path, changes)
    assert path.read_text(encoding="utf-8") == "server-name=Γεια\nallow-list=false\n"


@pytest.mark.parametrize(
    "changes",
    [
        {"difficulty": "impossible"},
        {"max-players": 0},
        {"max-players": "20"},
        {"pvp": "true"},
        {"server-port": 25565},
        {"motd": "x" * 1001},
    ],
)
def test_validate_rejects_bad_changes(changes):
    with pytest.raises(ValueError):
        validate_changes(changes, "minecraft-java")


def test_unsupported_server_type(java_props):
    assert not read_settings(java_props, "hytale")
    with pytest.raises(ValueError):
        validate_changes({"pvp": True}, "hytale")
