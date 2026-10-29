from types import SimpleNamespace

import pytest

from app.classes.helpers.java_memory import read_memory
from app.classes.installers.modded import ModdedInstaller


class FakeServers:
    def __init__(self):
        self.updated = []

    def update_server(self, server_obj):
        self.updated.append(server_obj)


@pytest.mark.parametrize(
    "loader, version, library",
    [
        ("forge", "1.20.1", "net/minecraftforge/forge/1.20.1-47.4.28"),
        ("neoforge", "21.1.264", "net/neoforged/neoforge/21.1.264"),
    ],
)
def test_args_file_servers_keep_the_wizard_memory(
    tmp_path, monkeypatch, loader, version, library
) -> None:
    # What the Forge and NeoForge installers write (1.17 to 1.20.2, NeoForge)
    (tmp_path / "run.sh").write_text(
        "#!/usr/bin/env sh\n"
        f'java @user_jvm_args.txt @libraries/{library}/unix_args.txt "$@"\n',
        encoding="utf-8",
    )
    server_obj = SimpleNamespace(
        path=str(tmp_path),
        executable=f"{loader}-installer-{version}.jar",
        execution_command=(
            f"java -Xms1000M -Xmx3000M -jar {loader}-installer-{version}.jar"
            " --installServer"
        ),
    )
    servers = FakeServers()
    installer = ModdedInstaller(
        SimpleNamespace(is_os_windows=lambda: False), servers, None
    )
    monkeypatch.setattr(installer, "_run_installer", lambda *args: None)

    installer.install(str(tmp_path), "id", server_obj)

    assert servers.updated == [server_obj]
    assert server_obj.execution_command == (
        "java @user_jvm_args.txt -Xms1000M -Xmx3000M"
        f" @libraries/{library}/unix_args.txt nogui"
    )
    # So the Config page can show and change it
    assert read_memory(server_obj.execution_command) == {
        "mem_min": 1000,
        "mem_max": 3000,
    }
    assert server_obj.executable.startswith(f"libraries/{library}/")
