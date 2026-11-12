from types import SimpleNamespace

from app.classes.helpers import modpacks
from app.classes.helpers.modrinth import ModrinthError
from app.classes.installers.modpack import ModpackInstaller
from app.classes.shared.server import ServerOutBuf


class FakeServers:
    def __init__(self):
        self.server_obj = SimpleNamespace(
            executable="server.jar", execution_command="java -jar server.jar nogui"
        )
        self.updated = []
        self.finished = []

    def get_server_obj(self, _server_id):
        return self.server_obj

    def update_server(self, server_obj):
        self.updated.append(server_obj.execution_command)

    def finish_import(self, server_id):
        self.finished.append(server_id)


class FakeSockets:
    clients = []
    sent = []

    def broadcast_to_server_users(self, server_id, event, data):
        self.sent.append((server_id, event, data))


class FakeModded:
    def __init__(self, works=True):
        self.works = works

    def install(self, _path, _server_id, server_obj):
        if self.works:
            server_obj.execution_command = "java @user_jvm_args.txt nogui"


def _installer(modded=None):
    FakeSockets.sent = []
    servers = FakeServers()
    helper = SimpleNamespace(find_java_installs=lambda: [])
    installer = ModpackInstaller(helper, servers, FakeSockets, modded or FakeModded())
    return installer, servers


DATA = {"mem_min": 2, "mem_max": 6, "server_properties_port": 25565}


def test_install_sets_the_command_and_removes_the_upload(tmp_path, monkeypatch):
    pack = tmp_path / "pack.mrpack"
    pack.write_bytes(b"x")
    seen = {}

    def build(root, pack_path, options, _say, _run):
        seen.update(root=root, pack=pack_path, options=options)
        return {
            "executable": "fabric.jar",
            "command": "java -jar fabric.jar nogui",
            "installer": False,
        }

    monkeypatch.setattr(modpacks, "build", build)
    installer, servers = _installer()
    assert installer.install("s1", tmp_path, DATA, pack) is True
    assert seen["options"]["port"] == 25565
    assert seen["options"]["source"] == {"site": "upload", "file": "pack.mrpack"}
    assert servers.server_obj.executable == "fabric.jar"
    assert servers.updated == ["java -jar fabric.jar nogui"]
    assert servers.finished == ["s1"]
    assert ("s1", "send_start_reload", {}) in FakeSockets.sent
    assert not pack.exists()


def test_install_runs_the_forge_installer(tmp_path, monkeypatch):
    monkeypatch.setattr(
        modpacks,
        "build",
        lambda *args: {
            "executable": "forge-installer-1.20.1.jar",
            "command": "java -jar forge-installer-1.20.1.jar --installServer",
            "installer": True,
        },
    )
    installer, servers = _installer()
    assert installer.install("s1", tmp_path, DATA, tmp_path / "p.mrpack") is True
    assert servers.server_obj.execution_command == "java @user_jvm_args.txt nogui"

    installer, servers = _installer(FakeModded(works=False))
    assert installer.install("s1", tmp_path, DATA, tmp_path / "p.mrpack") is False
    assert FakeSockets.sent[-1][1] == "send_error"
    assert servers.finished == ["s1"]


def test_install_from_modrinth_reports_errors(tmp_path, monkeypatch):
    def refuse(*_args):
        raise ModrinthError("NOT_FOUND", "This version is not from this modpack")

    monkeypatch.setattr(modpacks, "modrinth_pack", refuse)
    installer, servers = _installer()
    data = {**DATA, "project_id": "pack", "version_id": "v1"}
    assert installer.install("s1", tmp_path, data) is False
    assert servers.finished == ["s1"]
    assert FakeSockets.sent == [
        (
            "s1",
            "send_error",
            {
                "error": "The modpack could not be installed: "
                "This version is not from this modpack"
            },
        )
    ]


def test_the_terminal_keeps_the_install_lines(tmp_path, monkeypatch):
    def refuse(*_args):
        raise ModrinthError("NOT_FOUND", "This version is not from this modpack")

    monkeypatch.setattr(modpacks, "modrinth_pack", refuse)
    monkeypatch.setattr(ServerOutBuf, "lines", {})
    monkeypatch.setattr(ServerOutBuf, "total", {})
    installer, _servers = _installer()
    data = {**DATA, "project_id": "pack", "version_id": "v1"}
    installer.install("s1", tmp_path, data)
    assert ServerOutBuf.lines["s1"] == [
        "Downloading the modpack from Modrinth",
        "The modpack could not be installed: This version is not from this modpack",
    ]
    assert ServerOutBuf.total["s1"] == 2
