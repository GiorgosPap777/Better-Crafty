import hashlib
import os

import pytest

from app.classes.helpers import datapacks, modrinth


def _world(tmp_path, name="world"):
    (tmp_path / "server.properties").write_text(f"level-name={name}\n")
    folder = tmp_path / name / "datapacks"
    folder.mkdir(parents=True)
    return folder


def test_lists_zips_and_pack_folders(tmp_path):
    folder = _world(tmp_path)
    (folder / "b.zip").write_bytes(b"bb")
    (folder / "a.zip.disabled").write_bytes(b"a")
    (folder / "notes.txt").write_text("not a pack")
    (folder / ".hidden.zip").write_bytes(b"h")
    (folder / "pack").mkdir()
    (folder / "pack" / "pack.mcmeta").write_text("{}")
    (folder / "pack" / "data").mkdir()
    (folder / "pack" / "data" / "x.json").write_text("12345")
    (folder / "empty").mkdir()
    os.symlink(tmp_path / "server.properties", folder / "link.zip")
    packs = datapacks.local_packs(tmp_path)
    assert [(p["file"], p["enabled"], p["folder"]) for p in packs] == [
        ("a.zip.disabled", False, False),
        ("b.zip", True, False),
        ("pack", True, True),
    ]
    assert packs[1]["size"] == 2
    assert packs[2]["size"] == 7


def test_the_world_follows_level_name(tmp_path):
    folder = _world(tmp_path, "survival")
    (folder / "a.zip").write_bytes(b"a")
    assert [p["file"] for p in datapacks.local_packs(tmp_path)] == ["a.zip"]
    assert datapacks.world_folder(tmp_path).name == "survival"
    # No world yet: nothing to list
    (tmp_path / "server.properties").write_text("level-name=new\n")
    assert not datapacks.local_packs(tmp_path)


def test_refuses_a_world_or_folder_outside_the_server(tmp_path):
    server = tmp_path / "server"
    server.mkdir()
    (server / "server.properties").write_text("level-name=../elsewhere\n")
    with pytest.raises(modrinth.ModrinthError) as ex:
        datapacks.pack_folder(server)
    assert ex.value.code == "BAD_FOLDER"
    (server / "server.properties").write_text("level-name=world\n")
    (server / "world").mkdir()
    (tmp_path / "outside").mkdir()
    os.symlink(tmp_path / "outside", server / "world" / "datapacks")
    with pytest.raises(modrinth.ModrinthError) as ex:
        datapacks.local_packs(server)
    assert ex.value.code == "BAD_FOLDER"


def test_turn_a_pack_off_on_and_remove_it(tmp_path):
    folder = _world(tmp_path)
    (folder / "a.zip").write_bytes(b"a")
    (folder / "pack").mkdir()
    (folder / "pack" / "pack.mcmeta").write_text("{}")
    assert datapacks.change_pack(tmp_path, "a.zip", "disable") == "a.zip.disabled"
    assert datapacks.change_pack(tmp_path, "a.zip.disabled", "disable") == (
        "a.zip.disabled"
    )
    assert datapacks.change_pack(tmp_path, "a.zip.disabled", "enable") == "a.zip"
    assert (folder / "a.zip").exists()
    with pytest.raises(modrinth.ModrinthError) as ex:
        datapacks.change_pack(tmp_path, "pack", "disable")
    assert ex.value.code == "INVALID_ACTION"
    assert datapacks.change_pack(tmp_path, "pack", "remove") is None
    assert datapacks.change_pack(tmp_path, "a.zip", "remove") is None
    assert not list(folder.iterdir())


@pytest.mark.parametrize(
    "name, action, code",
    [
        ("missing.zip", "remove", "FILE_NOT_FOUND"),
        ("../server.properties", "remove", "FILE_NOT_FOUND"),
        ("notes.txt", "remove", "FILE_NOT_FOUND"),
        ("a.zip", "delete", "INVALID_ACTION"),
    ],
)
def test_change_refuses_other_files(tmp_path, name, action, code):
    folder = _world(tmp_path)
    (folder / "a.zip").write_bytes(b"a")
    (folder / "notes.txt").write_text("x")
    with pytest.raises(modrinth.ModrinthError) as ex:
        datapacks.change_pack(tmp_path, name, action)
    assert ex.value.code == code
    assert (tmp_path / "server.properties").exists()


def _file(name, data, primary=True, url=None):
    return {
        "primary": primary,
        "url": url or f"https://cdn.modrinth.com/data/x/{name}",
        "filename": name,
        "size": len(data),
        "hashes": {"sha512": hashlib.sha512(data).hexdigest()},
    }


def _version(project, version_id, data, deps=()):
    return {
        "id": version_id,
        "project_id": project,
        "version_number": version_id,
        "version_type": "release",
        "loaders": ["datapack"],
        "dependencies": [
            {"project_id": dep, "dependency_type": "required"} for dep in deps
        ],
        "files": [_file(f"{project}-{version_id}.zip", data)],
    }


def test_pack_file_takes_the_zip():
    version = {"files": [_file("mod.jar", b"j"), _file("pack.zip", b"z", False)]}
    assert datapacks.pack_file(version)["filename"] == "pack.zip"
    with pytest.raises(modrinth.ModrinthError) as ex:
        datapacks.pack_file({"files": [_file("mod.jar", b"j")]})
    assert ex.value.code == "NO_FILE"
    elsewhere = {"files": [_file("pack.zip", b"z", url="https://example.com/p.zip")]}
    with pytest.raises(modrinth.ModrinthError) as ex:
        datapacks.pack_file(elsewhere)
    assert ex.value.code == "BAD_FILE"
    sneaky = {"files": [_file("../pack.zip", b"z")]}
    with pytest.raises(modrinth.ModrinthError):
        datapacks.pack_file(sneaky)


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


def _fake_modrinth(monkeypatch, versions, files, present=(), calls=None):
    """Answer Modrinth calls from these dicts: versions by project."""

    def fake_get(url, **params):
        if calls is not None:
            calls.append((url, params))
        if url.endswith("/projects"):
            return [{"id": "lib", "title": "Library"}]
        project = url.split("/project/")[1].split("/")[0]
        return versions.get(project, [])

    monkeypatch.setattr(modrinth, "_get", fake_get)
    monkeypatch.setattr(datapacks, "installed", lambda *args: list(present))
    monkeypatch.setattr(
        modrinth.requests,
        "get",
        lambda url, **kwargs: _Response(files[url.rsplit("/", 1)[1]]),
    )


def test_install_puts_the_zip_in_the_world(tmp_path, monkeypatch):
    (tmp_path / "server.properties").write_text("level-name=world\n")
    calls = []
    versions = {"terralith": [_version("terralith", "2.5.8", b"zip")]}
    _fake_modrinth(monkeypatch, versions, {"terralith-2.5.8.zip": b"zip"}, calls=calls)
    result = datapacks.install(tmp_path, "1.21.1", "terralith", "s1")
    assert result["installed"][0]["file"] == "terralith-2.5.8.zip"
    assert result["missing"] == []
    folder = tmp_path / "world" / "datapacks"
    assert (folder / "terralith-2.5.8.zip").read_bytes() == b"zip"
    assert calls[0][1] == {"loaders": '["datapack"]', "game_versions": '["1.21.1"]'}


def test_install_replaces_a_turned_off_pack(tmp_path, monkeypatch):
    folder = _world(tmp_path)
    (folder / "terralith-2.5.7.zip.disabled").write_bytes(b"old")
    old = {
        "file": "terralith-2.5.7.zip.disabled",
        "project_id": "terralith",
        "version_id": "2.5.7",
        "enabled": False,
    }
    versions = {"terralith": [_version("terralith", "2.5.8", b"new")]}
    _fake_modrinth(monkeypatch, versions, {"terralith-2.5.8.zip": b"new"}, [old])
    result = datapacks.install(tmp_path, "1.21.1", "terralith", "s1")
    assert result["installed"][0]["replaced"] == "terralith-2.5.7.zip.disabled"
    assert [p.name for p in folder.iterdir()] == ["terralith-2.5.8.zip"]


def test_install_says_up_to_date_and_names_missing_packs(tmp_path, monkeypatch):
    folder = _world(tmp_path)
    (folder / "a-1.zip").write_bytes(b"a")
    present = {"file": "a-1.zip", "project_id": "a", "version_id": "1", "enabled": True}
    versions = {"a": [_version("a", "1", b"a", deps=["lib"])]}
    _fake_modrinth(monkeypatch, versions, {}, [present])
    result = datapacks.install(tmp_path, "1.21.1", "a", "s1")
    assert result["installed"][0]["up_to_date"] is True
    assert result["missing"] == []

    versions = {"b": [_version("b", "2", b"b", deps=["lib"])]}
    _fake_modrinth(monkeypatch, versions, {"b-2.zip": b"b"})
    result = datapacks.install(tmp_path, "1.21.1", "b", "s1")
    assert [item["file"] for item in result["installed"]] == ["b-2.zip"]
    assert result["missing"] == ["Library"]


def test_install_refuses_a_version_that_is_not_a_pack(tmp_path, monkeypatch):
    (tmp_path / "server.properties").write_text("level-name=world\n")
    _fake_modrinth(monkeypatch, {"a": [_version("a", "1", b"a")]}, {})
    with pytest.raises(modrinth.ModrinthError) as ex:
        datapacks.install(tmp_path, "1.21.1", "a", "s1", "other")
    assert ex.value.code == "NO_COMPATIBLE_VERSION"
    with pytest.raises(modrinth.ModrinthError) as ex:
        datapacks.install(tmp_path, "1.21.1", "a", "s1", "bad/id")
    assert ex.value.code == "INVALID_VERSION_ID"
    with pytest.raises(modrinth.ModrinthError) as ex:
        datapacks.install(tmp_path, "1.21.1", "none", "s1")
    assert ex.value.code == "NO_COMPATIBLE_VERSION"
    assert not (tmp_path / "world").exists()


def test_search_asks_for_data_packs(monkeypatch):
    seen = {}

    def fake_search(facets, query, offset):
        seen.update(facets=facets, query=query, offset=offset)
        return {"hits": []}

    monkeypatch.setattr(modrinth, "search_projects", fake_search)
    datapacks.search("1.21.1", "trees", 20)
    assert seen == {
        "facets": [["project_type:datapack"], ["versions:1.21.1"]],
        "query": "trees",
        "offset": 20,
    }
    datapacks.search(None)
    assert seen["facets"] == [["project_type:datapack"]]


def test_installed_names_the_zips_from_modrinth(tmp_path, monkeypatch):
    folder = _world(tmp_path)
    (folder / "terralith.zip").write_bytes(b"zip")
    (folder / "own.zip").write_bytes(b"own")
    (folder / "pack").mkdir()
    (folder / "pack" / "pack.mcmeta").write_text("{}")
    sha1 = hashlib.sha1(b"zip").hexdigest()
    posted = []

    def fake_post(url, body):
        posted.append((url.rsplit("/", 1)[1], body))
        if url.endswith("/update"):
            return {sha1: {"id": "v2", "version_number": "2.5.8"}}
        return {
            sha1: {"id": "v1", "project_id": "terralith", "version_number": "2.5.7"}
        }

    monkeypatch.setattr(modrinth, "_post", fake_post)
    monkeypatch.setattr(
        modrinth,
        "_get",
        lambda url, **params: [{"id": "terralith", "title": "Terralith"}],
    )
    packs = {p["file"]: p for p in datapacks.installed(tmp_path, "1.21.1")}
    assert packs["terralith.zip"]["title"] == "Terralith"
    assert packs["terralith.zip"]["update"] == "2.5.8"
    assert packs["own.zip"]["project_id"] is None
    assert "sha1" not in packs["pack"]
    assert len(posted[0][1]["hashes"]) == 2
    assert posted[1][1]["loaders"] == ["datapack"]
    assert posted[1][1]["game_versions"] == ["1.21.1"]
