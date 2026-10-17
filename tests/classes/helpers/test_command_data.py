from app.classes.helpers import command_data


def test_java_versions_oldest_first():
    versions = command_data.java_versions()
    assert versions, "no command data files shipped"
    keys = [tuple(int(p) for p in v.split(".")) for v in versions]
    assert keys == sorted(keys)
    # 1.21.10 sorts after 1.21.4, not between 1.21.1 and 1.21.4
    assert versions.index("1.21.10") > versions.index("1.21.4")


def test_every_version_has_its_file():
    for version in command_data.java_versions():
        assert (command_data.DATA_DIR / f"java-{version}.json").is_file()


def test_missing_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(command_data, "DATA_DIR", tmp_path / "missing")
    command_data.java_versions.cache_clear()
    try:
        assert not command_data.java_versions()
    finally:
        command_data.java_versions.cache_clear()
