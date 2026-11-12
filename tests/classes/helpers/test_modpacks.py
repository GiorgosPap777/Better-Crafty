import hashlib
import json
import zipfile

import pytest

from app.classes.helpers import modpacks
from app.classes.helpers.modrinth import ModrinthError


def _file(path, data: bytes, server="required", url=None):
    return {
        "path": path,
        "hashes": {
            "sha1": hashlib.sha1(data).hexdigest(),
            "sha512": hashlib.sha512(data).hexdigest(),
        },
        "env": {"client": "required", "server": server},
        "downloads": [url or f"https://cdn.modrinth.com/data/x/{path}"],
        "fileSize": len(data),
    }


def _index(files=(), **dependencies):
    return {
        "formatVersion": 1,
        "game": "minecraft",
        "versionId": "1.2.0",
        "name": "Test Pack",
        "summary": "A pack for tests",
        "files": list(files),
        "dependencies": dependencies
        or {"minecraft": "1.21.1", "fabric-loader": "0.16.10"},
    }


def _pack(path, index, extra=None):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(modpacks.INDEX, json.dumps(index))
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return path


def _read(tmp_path, index, extra=None):
    with zipfile.ZipFile(_pack(tmp_path / "p.mrpack", index, extra)) as archive:
        return modpacks.read_index(archive)


@pytest.mark.parametrize(
    "path, ok",
    [
        ("mods/a.jar", True),
        ("config/a b's.toml", True),
        ("a.jar", True),
        ("../a.jar", False),
        ("mods/../../a.jar", False),
        ("/etc/passwd", False),
        ("C:/a.jar", False),
        ("mods\\a.jar", False),
        ("mods//a.jar", False),
        ("./a.jar", False),
        ("mods/", False),
        ("", False),
        (None, False),
    ],
)
def test_safe_path(path, ok):
    assert (modpacks.safe_path(path) is not None) == ok


def test_read_index(tmp_path):
    pack = _read(
        tmp_path,
        _index(
            [
                _file("mods/a.jar", b"a"),
                _file("mods/menu.jar", b"m", server="unsupported"),
                _file("resourcepacks/look.zip", b"r"),
                _file("shaderpacks/sun.zip", b"s", server="optional"),
                _file("mods/b.jar", b"b", server="optional"),
                _file("mods/c.jar", b"c", url="https://github.com/x/c.jar"),
            ]
        ),
    )
    assert pack["name"] == "Test Pack"
    assert pack["version"] == "1.2.0"
    assert (pack["minecraft"], pack["loader"], pack["loader_version"]) == (
        "1.21.1",
        "fabric",
        "0.16.10",
    )
    assert [f["path"] for f in pack["files"]] == [
        "mods/a.jar",
        "mods/b.jar",
        "mods/c.jar",
    ]
    assert pack["files"][2]["url"] == "https://github.com/x/c.jar"
    assert (pack["file_count"], pack["size"], pack["skipped"]) == (3, 3, 3)


def test_read_index_vanilla_and_loaders(tmp_path):
    assert _read(tmp_path, _index(minecraft="1.20.1"))["loader"] == "vanilla"
    for key, loader in modpacks.LOADERS.items():
        pack = _read(tmp_path, _index(**{"minecraft": "1.20.1", key: "47.3.0"}))
        assert pack["loader"] == loader


@pytest.mark.parametrize(
    "change, code",
    [
        (lambda i: i.update(formatVersion=2), "BAD_PACK"),
        (lambda i: i.update(game="other"), "BAD_PACK"),
        (lambda i: i.update(dependencies={"fabric-loader": "1"}), "BAD_PACK"),
        (
            lambda i: i.update(dependencies={"minecraft": "1.7.10", "liteloader": "1"}),
            "UNSUPPORTED_LOADER",
        ),
        (
            lambda i: i["dependencies"].update({"forge": "47.3.0"}),
            "UNSUPPORTED_LOADER",
        ),
        (lambda i: i["dependencies"].update({"fabric-loader": "0.1 ; x"}), "BAD_PACK"),
        (lambda i: i["files"].append(_file("../evil.jar", b"x")), "BAD_PACK"),
        (lambda i: i["files"].append(_file("/evil.jar", b"x")), "BAD_PACK"),
        (
            lambda i: i["files"].append(
                _file("mods/x.jar", b"x", url="https://evil.example/x.jar")
            ),
            "BAD_PACK",
        ),
        (
            lambda i: i["files"].append(
                _file("mods/x.jar", b"x", url="http://cdn.modrinth.com/x.jar")
            ),
            "BAD_PACK",
        ),
        (
            lambda i: i["files"].append(
                {**_file("mods/x.jar", b"x"), "hashes": {"sha1": "00"}}
            ),
            "BAD_PACK",
        ),
    ],
)
def test_read_index_refuses(tmp_path, change, code):
    index = _index()
    change(index)
    with pytest.raises(ModrinthError) as found:
        _read(tmp_path, index)
    assert found.value.code == code


def test_not_a_modpack(tmp_path):
    path = tmp_path / "x.mrpack"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("server.jar", b"x")
    with pytest.raises(ModrinthError) as found:
        modpacks.summary(path)
    assert found.value.code == "NOT_A_MODPACK"
    path.write_bytes(b"not a zip")
    with pytest.raises(ModrinthError):
        modpacks.summary(path)


def test_summary_leaves_out_the_file_list(tmp_path):
    path = _pack(tmp_path / "p.mrpack", _index([_file("mods/a.jar", b"a")]))
    found = modpacks.summary(path)
    assert "files" not in found
    assert found["file_count"] == 1
    assert found["loader_name"] == "Fabric"


def test_copy_overrides(tmp_path):
    path = _pack(
        tmp_path / "p.mrpack",
        _index(),
        {
            "overrides/config/a.toml": "pack",
            "overrides/config/b.toml": "pack",
            "server-overrides/config/b.toml": "server",
            "client-overrides/options.txt": "client",
            "overrides/resourcepacks/look.zip": "r",
            "overrides/kubejs/": "",
        },
    )
    root = tmp_path / "server"
    root.mkdir()
    with zipfile.ZipFile(path) as archive:
        assert modpacks.copy_overrides(archive, root) == 3
    assert (root / "config" / "a.toml").read_text() == "pack"
    assert (root / "config" / "b.toml").read_text() == "server"
    assert not (root / "options.txt").exists()
    assert not (root / "resourcepacks").exists()


def test_copy_overrides_refuses_unsafe_names(tmp_path):
    path = _pack(tmp_path / "p.mrpack", _index(), {"overrides/../evil.txt": "x"})
    root = tmp_path / "server"
    root.mkdir()
    with zipfile.ZipFile(path) as archive, pytest.raises(ModrinthError):
        modpacks.copy_overrides(archive, root)
    assert not (tmp_path / "evil.txt").exists()


def test_set_property(tmp_path):
    path = tmp_path / "server.properties"
    modpacks.set_property(path, "server-port", 25570)
    assert path.read_text() == "server-port=25570\n"
    path.write_text("#server-port=1\nmotd=Hi\nserver-port = 25565\n")
    modpacks.set_property(path, "server-port", 25570)
    assert path.read_text() == "#server-port=1\nmotd=Hi\nserver-port=25570\n"


def _java(tmp_path, folder, version=None):
    home = tmp_path / folder
    (home / "bin").mkdir(parents=True)
    if version:
        (home / "release").write_text(f'IMPLEMENTOR="x"\nJAVA_VERSION="{version}"\n')
    return str(home / "bin" / "java")


def test_java_major(tmp_path):
    assert modpacks.java_major(_java(tmp_path, "openjdk", "17.0.2")) == 17
    assert modpacks.java_major(_java(tmp_path, "old", "1.8.0_402")) == 8
    assert modpacks.java_major("/usr/lib/jvm/java-21-openjdk-amd64/bin/java") == 21
    assert modpacks.java_major("/usr/lib/jvm/java-1.8.0-openjdk/jre/bin/java") == 8
    assert modpacks.java_major("/usr/lib/jvm/temurin-17-jdk-amd64/bin/java") == 17
    assert modpacks.java_major("/usr/bin/java") is None


@pytest.mark.parametrize(
    "minecraft, java",
    [
        ("1.12.2", 8),
        ("1.16.5", 8),
        ("1.17.1", 16),
        ("1.18.2", 17),
        ("1.20.4", 17),
        ("1.20.5", 21),
        ("1.21.1", 21),
        ("26.1", 25),
        ("24w14a", 21),
    ],
)
def test_required_java(minecraft, java):
    assert modpacks.required_java(minecraft) == java


def test_required_java_asks_mojang_first():
    assert modpacks.required_java("1.20.1", {"javaVersion": {"majorVersion": 17}}) == 17


def test_pick_java():
    installs = [
        "/usr/lib/jvm/java-21-openjdk-amd64/bin/java",
        "/usr/lib/jvm/java-8-openjdk-amd64/jre/bin/java",
        "/usr/lib/jvm/java-17-openjdk-amd64/bin/java",
        "",
    ]
    assert modpacks.pick_java(8, installs)[1] == 8
    assert modpacks.pick_java(16, installs) == (installs[2], 17)
    assert modpacks.pick_java(25, installs) == ("java", None)
    assert modpacks.pick_java(17, []) == ("java", None)
    assert modpacks.java_word(installs[2]) == f'"{installs[2]}"'
    assert modpacks.java_word("java") == "java"


def test_forge_installer_urls():
    assert modpacks.forge_installer_urls("forge", "1.20.1", "47.3.0")[0] == (
        "https://maven.minecraftforge.net/net/minecraftforge/forge/"
        "1.20.1-47.3.0/forge-1.20.1-47.3.0-installer.jar"
    )
    assert modpacks.forge_installer_urls("forge", "1.7.10", "10.13.4.1614")[1] == (
        "https://maven.minecraftforge.net/net/minecraftforge/forge/"
        "1.7.10-10.13.4.1614-1.7.10/forge-1.7.10-10.13.4.1614-1.7.10-installer.jar"
    )
    assert modpacks.forge_installer_urls("neoforge", "1.21.1", "21.1.77") == [
        "https://maven.neoforged.net/releases/net/neoforged/neoforge/"
        "21.1.77/neoforge-21.1.77-installer.jar"
    ]
    assert modpacks.forge_installer_urls("neoforge", "1.20.1", "47.1.106") == [
        "https://maven.neoforged.net/releases/net/neoforged/forge/"
        "1.20.1-47.1.106/forge-1.20.1-47.1.106-installer.jar"
    ]


class _Response:
    def __init__(self, data, status=200):
        self.status_code = status
        self.data = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.text = self.data.decode(errors="replace")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def json(self):
        return json.loads(self.data)

    def iter_content(self, _size):
        yield self.data


SERVER_JAR = b"vanilla server"
MOJANG = {
    modpacks.MOJANG_MANIFEST: {
        "versions": [
            {
                "id": "1.21.1",
                "url": "https://piston-meta.mojang.com/v1/packages/x/1.21.1.json",
            }
        ]
    },
    "https://piston-meta.mojang.com/v1/packages/x/1.21.1.json": {
        "javaVersion": {"majorVersion": 21},
        "downloads": {
            "server": {
                "url": "https://piston-data.mojang.com/v1/objects/x/server.jar",
                "sha1": hashlib.sha1(SERVER_JAR).hexdigest(),
            }
        },
    },
    "https://piston-data.mojang.com/v1/objects/x/server.jar": SERVER_JAR,
    f"{modpacks.FABRIC_META}/versions/installer": [
        {"version": "1.1.3", "stable": False},
        {"version": "1.1.2", "stable": True},
    ],
    f"{modpacks.FABRIC_META}/versions/loader/1.21.1/0.16.10/1.1.2/server/jar": (
        b"fabric launcher"
    ),
}


def _web(monkeypatch, answers):
    asked = []

    def fake_get(url, **_kwargs):
        asked.append(url)
        if url not in answers:
            return _Response(b"missing", 404)
        return _Response(answers[url])

    monkeypatch.setattr(modpacks.requests, "get", fake_get)
    return asked


def _options(tmp_path, **more):
    return {
        "mem_min": 2,
        "mem_max": 6,
        "port": 25570,
        "java_installs": [_java(tmp_path, "java-21", "21.0.5")],
        "source": {"site": "upload", "file": "p.mrpack"},
        **more,
    }


def test_build_a_fabric_server(tmp_path, monkeypatch):
    files = [
        _file("mods/a.jar", b"mod a"),
        _file("mods/menu.jar", b"menu", server="unsupported"),
        _file("config/b.toml", b"from files"),
    ]
    answers = dict(MOJANG)
    answers["https://cdn.modrinth.com/data/x/mods/a.jar"] = b"mod a"
    answers["https://cdn.modrinth.com/data/x/config/b.toml"] = b"from files"
    asked = _web(monkeypatch, answers)
    path = _pack(
        tmp_path / "p.mrpack",
        _index(files),
        {
            "overrides/config/b.toml": "from overrides",
            "overrides/server.properties": "motd=Pack\nserver-port=25565\n",
            "overrides/eula.txt": "eula=true\n",
        },
    )
    root = tmp_path / "server"
    root.mkdir()
    said = []
    result = modpacks.build(root, path, _options(tmp_path), said.append, None)

    java = tmp_path / "java-21" / "bin" / "java"
    jar = "fabric-server-mc.1.21.1-loader.0.16.10-launcher.1.1.2.jar"
    assert result == {
        "executable": jar,
        "command": f'"{java}" -Xms2048M -Xmx6144M -jar {jar} nogui',
        "installer": False,
    }
    assert (root / jar).read_bytes() == b"fabric launcher"
    assert (root / "mods" / "a.jar").read_bytes() == b"mod a"
    assert not (root / "mods" / "menu.jar").exists()
    assert "https://cdn.modrinth.com/data/x/mods/menu.jar" not in asked
    # Overrides win over downloaded files, the wizard over the pack
    assert (root / "config" / "b.toml").read_text() == "from overrides"
    assert (root / "server.properties").read_text() == "motd=Pack\nserver-port=25570\n"
    assert (root / "eula.txt").read_text() == "eula=false\n"
    record = json.loads((root / modpacks.RECORD).read_text())
    assert record["name"] == "Test Pack"
    assert record["source"] == {"site": "upload", "file": "p.mrpack"}
    assert record["files"] == ["config/b.toml", "mods/a.jar"]
    assert any("Java 21" in line for line in said)
    assert sorted(p.name for p in root.iterdir() if p.name.startswith(".")) == []


def test_build_a_vanilla_server(tmp_path, monkeypatch):
    _web(monkeypatch, MOJANG)
    path = _pack(tmp_path / "p.mrpack", _index(minecraft="1.21.1"))
    root = tmp_path / "server"
    root.mkdir()
    result = modpacks.build(
        root, path, _options(tmp_path, agree_to_eula=True), lambda _: None, None
    )
    assert result["executable"] == "server.jar"
    assert (root / "server.jar").read_bytes() == SERVER_JAR
    assert (root / "eula.txt").read_text() == "eula=true\n"


def test_build_a_neoforge_server_leaves_the_installer_to_run(tmp_path, monkeypatch):
    answers = dict(MOJANG)
    url = modpacks.forge_installer_urls("neoforge", "1.21.1", "21.1.77")[0]
    answers[url] = b"installer"
    answers[url + ".sha1"] = hashlib.sha1(b"installer").hexdigest().encode()
    _web(monkeypatch, answers)
    path = _pack(tmp_path / "p.mrpack", _index(minecraft="1.21.1", neoforge="21.1.77"))
    root = tmp_path / "server"
    root.mkdir()
    result = modpacks.build(
        root, path, _options(tmp_path, java_installs=[]), lambda _: None, None
    )
    assert result == {
        "executable": "neoforge-installer-1.21.1.jar",
        "command": (
            "java -Xms2048M -Xmx6144M -jar neoforge-installer-1.21.1.jar"
            " --installServer"
        ),
        "installer": True,
    }
    assert (root / "neoforge-installer-1.21.1.jar").read_bytes() == b"installer"


def test_build_a_quilt_server_runs_its_installer(tmp_path, monkeypatch):
    answers = dict(MOJANG)
    url = "https://maven.quiltmc.org/repository/release/q/quilt-installer-0.15.1.jar"
    answers[f"{modpacks.QUILT_META}/versions/installer"] = [
        {"version": "0.9.0", "url": url.replace("0.15.1", "0.9.0")},
        {
            "version": "0.15.1",
            "url": url,
            "hashes": {"sha512": hashlib.sha512(b"quilt").hexdigest()},
        },
    ]
    answers[url] = b"quilt"
    _web(monkeypatch, answers)
    path = _pack(
        tmp_path / "p.mrpack", _index(minecraft="1.21.1", **{"quilt-loader": "0.27.1"})
    )
    root = tmp_path / "server"
    root.mkdir()
    ran = []

    def run(args):
        ran.append(args)
        assert (root / ".quilt-installer.jar").read_bytes() == b"quilt"
        (root / modpacks.QUILT_LAUNCHER).write_bytes(b"launcher")
        return 0

    result = modpacks.build(root, path, _options(tmp_path), lambda _: None, run)
    assert result["executable"] == modpacks.QUILT_LAUNCHER
    assert ran[0][1:8] == [
        "-jar",
        ".quilt-installer.jar",
        "install",
        "server",
        "1.21.1",
        "0.27.1",
        "--download-server",
    ]
    assert not (root / ".quilt-installer.jar").exists()


def test_build_stops_on_a_damaged_file(tmp_path, monkeypatch):
    answers = dict(MOJANG)
    answers["https://cdn.modrinth.com/data/x/mods/a.jar"] = b"something else"
    _web(monkeypatch, answers)
    path = _pack(tmp_path / "p.mrpack", _index([_file("mods/a.jar", b"mod a")]))
    root = tmp_path / "server"
    root.mkdir()
    with pytest.raises(ModrinthError) as found:
        modpacks.build(root, path, _options(tmp_path), lambda _: None, None)
    assert found.value.code == "BAD_CHECKSUM"
    assert "mods/a.jar" in str(found.value)
    assert not (root / "mods" / "a.jar").exists()


def test_build_refuses_an_unknown_minecraft_version(tmp_path, monkeypatch):
    _web(monkeypatch, MOJANG)
    path = _pack(tmp_path / "p.mrpack", _index(minecraft="9.9"))
    with pytest.raises(ModrinthError) as found:
        modpacks.build(tmp_path, path, _options(tmp_path), lambda _: None, None)
    assert found.value.code == "UNKNOWN_VERSION"


def _modrinth_version(**file):
    return {
        "id": "v1",
        "project_id": "pack",
        "files": [
            {
                "filename": "Pack 1.0.mrpack",
                "primary": True,
                "url": "https://cdn.modrinth.com/data/pack/versions/v1/Pack.mrpack",
                "hashes": {"sha512": "a" * 128},
                "size": 1000,
                **file,
            }
        ],
    }


def test_modrinth_pack(monkeypatch):
    monkeypatch.setattr(
        modpacks.modrinth, "get_version", lambda _id: _modrinth_version()
    )
    assert modpacks.modrinth_pack("pack", "v1")["sha512"] == "a" * 128
    with pytest.raises(ModrinthError):
        modpacks.modrinth_pack("other", "v1")
    for bad in (
        {"url": "https://evil.example/Pack.mrpack"},
        {"hashes": {}},
        {"filename": "Pack.zip"},
        {"size": modpacks.MAX_PACK_SIZE + 1},
    ):
        monkeypatch.setattr(
            modpacks.modrinth,
            "get_version",
            lambda _id, bad=bad: _modrinth_version(**bad),
        )
        with pytest.raises(ModrinthError):
            modpacks.modrinth_pack("pack", "v1")
