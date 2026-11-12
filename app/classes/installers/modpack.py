import html
import logging
import subprocess
import zipfile
from pathlib import Path

from app.classes.helpers import modpacks, modrinth
from app.classes.helpers.modrinth import ModrinthError
from app.classes.models.server_permissions import EnumPermissionsServer
from app.classes.shared.server import ServerOutBuf

logger = logging.getLogger(__name__)

PACK_FILE = ".crafty-modpack.mrpack"
# Install lines the Terminal keeps for when it is opened later
KEPT_LINES = 500


class ModpackInstaller:
    """Makes a new server from a Modrinth modpack, on its own thread. Its
    progress goes to the server's Terminal."""

    def __init__(self, helper, servers_controller, websocket_manager, modded):
        self.helper = helper
        self.servers_controller = servers_controller
        self.websocket_manager = websocket_manager
        self.modded_installer = modded

    def install(self, server_id, server_path, create_data: dict, pack_path=None):
        """create_data: project_id and version_id of a pack on Modrinth (when
        pack_path, an uploaded .mrpack, is None), mem_min, mem_max (GB),
        server_properties_port and agree_to_eula."""
        root = Path(server_path)
        error = None
        try:
            if pack_path is None:
                self._say(server_id, "Downloading the modpack from Modrinth")
                found = modpacks.modrinth_pack(
                    create_data["project_id"], create_data["version_id"]
                )
                pack_path = root / PACK_FILE
                modrinth.download(
                    found["url"],
                    pack_path,
                    found["sha512"],
                    max_size=modpacks.MAX_PACK_SIZE,
                )
                source = {
                    "site": "modrinth",
                    "project_id": create_data["project_id"],
                    "version_id": create_data["version_id"],
                }
            else:
                source = {"site": "upload", "file": Path(pack_path).name}
            options = {
                "mem_min": create_data["mem_min"],
                "mem_max": create_data["mem_max"],
                "port": create_data["server_properties_port"],
                "agree_to_eula": create_data.get("agree_to_eula", False),
                "java_installs": self.helper.find_java_installs(),
                "source": source,
            }
            result = modpacks.build(
                root,
                pack_path,
                options,
                lambda text: self._say(server_id, text),
                lambda args: self._run(server_id, root, args),
            )
            server_obj = self.servers_controller.get_server_obj(server_id)
            server_obj.executable = result["executable"]
            server_obj.execution_command = result["command"]
            self.servers_controller.update_server(server_obj)
            if result["installer"]:
                self._say(server_id, "Running the installer")
                self.modded_installer.install(root, server_id, server_obj)
                if "--installServer" in server_obj.execution_command:
                    raise ModrinthError(
                        "LOADER_FAILED",
                        "The installer failed; its .log file is in the server's"
                        " files",
                    )
            self._say(server_id, "The modpack is installed")
        except (ModrinthError, OSError, zipfile.BadZipFile) as ex:
            error = str(ex)
        except Exception as ex:  # pylint: disable=broad-exception-caught
            logger.exception("Modpack install for server %s failed", server_id)
            error = str(ex)
        finally:
            if pack_path is not None:
                Path(pack_path).unlink(missing_ok=True)
        self.servers_controller.finish_import(server_id)
        if error:
            self._say(server_id, f"The modpack could not be installed: {error}")
            self.websocket_manager().broadcast_to_server_users(
                server_id,
                "send_error",
                {"error": f"The modpack could not be installed: {error}"},
            )
            return False
        self.websocket_manager().broadcast_to_server_users(
            server_id, "notification", "Modpack installed"
        )
        self.websocket_manager().broadcast_to_server_users(
            server_id, "send_start_reload", {}
        )
        return True

    def _say(self, server_id, text: str):
        logger.info("Modpack for server %s: %s", server_id, text)
        # The Terminal reads these when it loads; the server's first start
        # replaces them with its own output
        key = str(server_id)
        kept = ServerOutBuf.lines.setdefault(key, [])
        kept.append(text)
        del kept[:-KEPT_LINES]
        ServerOutBuf.total[key] = ServerOutBuf.total.get(key, 0) + 1
        if self.websocket_manager().clients:
            self.websocket_manager().broadcast_page_params(
                "/panel/server_detail",
                {"id": server_id},
                "vterm_new_line",
                {"line": html.escape(text) + "<br />"},
                required_permission=EnumPermissionsServer.TERMINAL,
            )

    def _run(self, server_id, root: Path, args) -> int:
        with subprocess.Popen(
            args,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        ) as process:
            for line in process.stdout:
                if line.strip():
                    self._say(server_id, line.strip())
            return process.wait()
