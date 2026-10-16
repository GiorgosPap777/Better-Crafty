"""Make the test data the browser scripts in this folder expect.

Start a fresh Crafty first (its first start writes
app/config/default-creds.txt), then run, with Crafty's own Python:

    python dev/handoff-tools/setup_testdata.py --crafty-dir <folder Crafty runs in>

It logs in as admin, imports two servers that run the fake server in
fake_server/ (Java 8 or newer must be on the PATH), fills server 1 with sample
files, a log, player lists and player save files, makes a backup and a role,
adds the 2FA user "tester", and writes token, mfa.json and local.json next to this
script. Run it once per fresh Crafty; running it again adds two more servers.
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pyotp
import requests
import urllib3

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
XSS_NAME = "<img src=x onerror=window.__xss=1>.txt"

PROPERTIES = """#Minecraft server properties
#Thu Oct 15 07:38:41 UTC 2026
allow-flight=false
allow-nether=true
difficulty=easy
enable-command-block=false
enforce-whitelist=false
force-gamemode=false
gamemode=survival
hardcore=false
level-name=world
level-seed=
max-players=20
motd=§aA Minecraft Server
online-mode=true
pvp=true
server-port=25565
simulation-distance=10
spawn-protection=16
view-distance=10
white-list=false
"""
BANNED = [
    {
        "uuid": "11111111-2222-3333-4444-555555555555",
        "name": "Griefer99",
        "created": "2026-10-14 18:22:05 +0000",
        "source": "Server",
        "expires": "forever",
        "reason": "Destroyed spawn <b>bold</b>",
    }
]
OPS = [
    {
        "uuid": "853c80ef-3c37-49fd-aa49-938b674adae6",
        "name": "jeb_",
        "level": 4,
        "bypassesPlayerLimit": False,
    }
]
WHITELIST = [
    {"uuid": "069a79f4-44e9-4726-a5be-fca90e38aaf5", "name": "Notch"},
    {"uuid": "853c80ef-3c37-49fd-aa49-938b674adae6", "name": "jeb_"},
]


class Crafty:
    def __init__(self, url, token=None):
        self.url = url.rstrip("/")
        self.session = requests.Session()
        # Crafty's certificate is self-signed; also ignore proxy and CA settings
        # from the environment, which would override verify=False
        self.session.trust_env = False
        self.session.verify = False
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def call(self, method, path, **kwargs):
        response = self.session.request(method, self.url + path, timeout=60, **kwargs)
        try:
            body = response.json()
        except ValueError:
            body = response.text
        if response.status_code >= 400:
            sys.exit(f"{method} {path} failed ({response.status_code}): {body}")
        return body

    def login(self, username, password):
        body = self.call(
            "POST",
            "/api/v2/auth/login/",
            json={"username": username, "password": password},
        )
        return body["data"]["token"]


def wait_for(check, what, seconds=90):
    end = time.time() + seconds
    while time.time() < end:
        result = check()
        if result:
            return result
        time.sleep(1)
    sys.exit(f"Timed out waiting for {what}")


def same_owner(paths, reference):
    """When run as root (Linux), hand new files to the user Crafty runs as."""
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return
    stat = Path(reference).stat()
    for path in paths:
        for root, dirs, files in os.walk(path):
            for name in [root, *(os.path.join(root, n) for n in dirs + files)]:
                os.chown(name, stat.st_uid, stat.st_gid)
        os.chown(path, stat.st_uid, stat.st_gid)


def import_servers(api, crafty_dir):
    upload = crafty_dir / "import" / "upload"
    upload.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(upload / "fake.zip", "w") as archive:
        archive.write(HERE / "fake_server" / "server.jar", "server.jar")
        archive.writestr("eula.txt", "eula=true\n")
    same_owner([crafty_dir / "import"], crafty_dir)

    ids = []
    for name in ("Survival World", "Creative Build"):
        body = api.call(
            "POST",
            "/api/v2/servers/",
            json={
                "name": name,
                "monitoring_type": "minecraft_java",
                "minecraft_java_monitoring_data": {"host": "127.0.0.1", "port": 25565},
                "create_type": "minecraft_java",
                "minecraft_java_create_data": {
                    "create_type": "import_server",
                    "import_server_create_data": {
                        "archive_name": "fake.zip",
                        "archive_internal_path": "",
                        "jarfile": "server.jar",
                        "mem_min": 0.25,
                        "mem_max": 0.5,
                        "server_properties_port": 25565,
                    },
                },
            },
        )
        ids.append(body["data"]["new_server_id"])

    paths = []
    for server_id in ids:
        path = Path(api.call("GET", f"/api/v2/servers/{server_id}/")["data"]["path"])
        wait_for(lambda p=path: (p / "server.jar").exists(), f"the import of {path}")
        time.sleep(2)
        (path / "eula.txt").write_text("eula=true\n", encoding="utf-8")
        paths.append(path)
    return ids, paths


def fill_server_one(path, xss):
    (path / "server.properties").write_text(PROPERTIES, encoding="utf-8")
    for name, data in (
        ("banned-players.json", BANNED),
        ("ops.json", OPS),
        ("whitelist.json", WHITELIST),
    ):
        (path / name).write_text(json.dumps(data), encoding="utf-8")

    chat = "<img src=x onerror=window.__xss=3> hello" if xss else "hello everyone"
    (path / "logs").mkdir(exist_ok=True)
    (path / "logs" / "latest.log").write_text(
        "[10:00:00] [Server thread/INFO]: Starting minecraft server\n"
        "[10:00:01] [Server thread/WARN]: Can't keep up! Is the server overloaded?\n"
        f"[10:00:02] [Server thread/INFO]: <Steve> {chat}\n"
        "[10:00:03] [Server thread/INFO]: Done (3.2s)!\n",
        encoding="utf-8",
    )

    (path / "100% #1 & more.txt").write_text("hello\n", encoding="utf-8")
    # Windows does not allow < and > in file names
    if xss and os.name != "nt":
        (path / XSS_NAME).write_text("", encoding="utf-8")
    (path / "many").mkdir(exist_ok=True)
    for number in range(1, 521):
        (path / "many" / f"f{number}.txt").write_text(str(number), encoding="utf-8")
    (path / "world" / "data").mkdir(parents=True, exist_ok=True)
    (path / "world" / "data" / "world.txt").write_text("", encoding="utf-8")

    env = dict(os.environ, REPO=str(REPO))
    env.pop("XSS", None)
    if xss:
        env["XSS"] = "1"
    subprocess.run(
        [sys.executable, str(HERE / "player_fixtures.py"), str(path)],
        env=env,
        check=True,
    )


def make_backup(api, server_id):
    backups = api.call("GET", f"/api/v2/servers/{server_id}/backups/")
    default = next(b for b in backups.values() if b.get("default"))
    backup_id = default["backup_id"]
    folder = Path(default["backup_location"]) / backup_id
    api.call("POST", f"/api/v2/servers/{server_id}/action/backup_server/{backup_id}/")
    wait_for(
        lambda: folder.is_dir() and any(folder.iterdir()),
        "the backup",
    )
    return backup_id


def make_role(api, server_id):
    api.call(
        "POST",
        "/api/v2/roles/",
        json={
            "name": "Moderators",
            "servers": [{"server_id": server_id, "permissions": "11111111"}],
        },
    )


def make_mfa_user(api, url):
    user_id = api.call(
        "POST",
        "/api/v2/users/",
        json={"username": "tester", "password": "TesterPass123", "superuser": True},
    )["data"]["user_id"]
    # Tokens issued in the same second as a user change are refused
    time.sleep(2)
    tester = Crafty(url, Crafty(url).login("tester", "TesterPass123"))
    otp = tester.call("POST", f"/api/v2/users/{user_id}/totp/")["data"]["otp"]
    secret = otp.get("secret") or otp.get("totp_secret")
    body = tester.call(
        "POST",
        f"/api/v2/users/@me/totp/{otp['id']}/verify/",
        json={"name": "Phone", "totp": int(pyotp.TOTP(secret).now())},
    )
    return {"secret": secret, "backup": body["data"]["backup_codes"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument(
        "--crafty-dir",
        type=Path,
        default=REPO,
        help="the folder Crafty runs in (default: this repository)",
    )
    parser.add_argument("--url", default="https://localhost:8443")
    parser.add_argument(
        "--password", help="admin password (default: from default-creds.txt)"
    )
    parser.add_argument(
        "--no-xss",
        dest="xss",
        action="store_false",
        help="plain player, chat and file names (for screenshots)",
    )
    args = parser.parse_args()
    if not importlib.util.find_spec("pytest"):
        # player_fixtures.py borrows the NBT writer from the pytest tests
        sys.exit("pytest is missing: pip install pytest black pylint")
    urllib3.disable_warnings()
    crafty_dir = args.crafty_dir.resolve()

    password = args.password
    if not password:
        creds = crafty_dir / "app" / "config" / "default-creds.txt"
        password = json.loads(creds.read_text(encoding="utf-8"))["password"]
    token = Crafty(args.url).login("admin", password)
    (HERE / "token").write_text(token, encoding="utf-8")
    api = Crafty(args.url, token)

    ids, paths = import_servers(api, crafty_dir)
    fill_server_one(paths[0], args.xss)
    same_owner(paths, paths[0].parent)
    backup_id = make_backup(api, ids[0])
    make_role(api, ids[0])

    mfa = make_mfa_user(api, args.url)
    (HERE / "mfa.json").write_text(json.dumps(mfa), encoding="utf-8")
    (HERE / "backup_idx").unlink(missing_ok=True)

    settings = {
        "url": args.url,
        "craftyDir": str(crafty_dir),
        "S1": ids[0],
        "S2": ids[1],
        "B1": backup_id,
    }
    (HERE / "local.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
    print(json.dumps(settings, indent=2))
    print("Wrote token, mfa.json and local.json in", HERE)


if __name__ == "__main__":
    main()
