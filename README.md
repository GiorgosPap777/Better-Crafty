# Better Crafty

> A fork of [Crafty Controller](https://craftycontrol.com) 4.11.0 with a reworked
> login screen, easier server management pages and a long list of bug and
> security fixes.

![A Minecraft server's Terminal in Better Crafty](docs/screenshots/terminal-after.png)

Crafty Controller is a web control panel for Minecraft servers: it runs your
servers in the background and gives you a website to start, stop, configure
and back them up. **Better Crafty is the same program**, with changes to the
parts people use every day. It uses the same folders and database as Crafty
4.11.0, so it can take over an existing install, and you can go back to the
original later ([Moving from Crafty Controller](#moving-from-crafty-controller)).

This fork is not made by or affiliated with the Crafty Controller team.
Please report problems with this fork here, not to them.

**Contents:** [What changed](#what-changed) ·
[Before and after screenshots](#before-and-after) ·
[Bug fixes](#bug-fixes) · [Security fixes](#security-fixes) ·
[Install](#install) · [Updating](#updating) ·
[Moving from Crafty Controller](#moving-from-crafty-controller) ·
[Credits and license](#credits-and-license)

## What changed

| Area | In short |
|---|---|
| **Login** | Rebuilt page: a separate two-factor step, show password, a countdown after too many failed tries, several login bugs fixed. |
| **Server page header** | The same header on every server tab: status, Start / Restart / Stop, live uptime, CPU, memory, players and version. A restart can warn the players in the game first, also from a schedule. |
| **Terminal** | Command suggestions like the game's chat box (press Tab), auto-scroll switch, command history with the ↑ and ↓ keys, a cap of 2,000 lines so the page stays fast, a link to older logs. |
| **Config** | Split into sections. Game settings (`server.properties`) and memory are normal form fields now, so no more editing the file or the Java command by hand. |
| **Players** | Everyone who has ever joined, with play time and last seen. Each player opens to their inventory, armor, ender chest, statistics and advancements. Whitelist, operators and bans in one place. |
| **Backups** | Shows the last backup (time and size) and how many copies are kept. Buttons have labels. Restore errors are shown, and restoring a snapshot asks first. |
| **Off-site backups** | Each zip backup can be copied automatically to another disk, a network share or S3-compatible cloud storage (AWS S3, Backblaze B2, Cloudflare R2, MinIO, ...), keeping as many copies there as you choose. Copies can be brought back and restored with one click. |
| **World** | A new tab: the world's version, seed and size, a one-click download of the world as a zip (even while the server runs), and a reset of the Nether or the End (the dragon comes back). |
| **Files** | A clickable folder path, readable file types, a menu button on each row, and a layout that works on phones. |
| **Metrics** | Separate CPU, memory and player charts that zoom together, with quick time ranges. |
| **Logs** | A "hide lines containing" filter, a clear message when there is no log, and links between Logs and Terminal. |
| **Phones** | Smaller server header, and pages that fit a phone screen without sideways scrolling. |

## Before and after

All screenshots are of the same test server. **Before** is Crafty 4.11.0,
**after** is Better Crafty. Click an image to see it full size.

### Login

The two-factor code box only appears when your account needs it. There is a
show password button, and the page counts down when too many failed tries
lock the login for a while.

| Before | After |
|---|---|
| ![Login page in Crafty 4.11.0](docs/screenshots/login-before.jpg) | ![Login page in Better Crafty](docs/screenshots/login-after.jpg) |

### Server page header and Terminal

Status, controls and live numbers sit at the top of every server tab. The
buttons show "starting" and "stopping" while they work, and Kill sits in the
⋮ menu behind a confirmation. Memory is shown in MB or GB.

| Before | After |
|---|---|
| ![Server terminal page in Crafty 4.11.0](docs/screenshots/terminal-before.png) | ![Server terminal page in Better Crafty](docs/screenshots/terminal-after.png) |

### Command suggestions

Typing a command in the Terminal works like the chat box in Minecraft Java:
a list pops up with the commands, player names, items, blocks, effects,
game rules and so on that fit, and a hint such as `<item> [<count>]` shows
what comes next. **Tab** takes the highlighted suggestion, **↑** and **↓**
move through the list, and **Esc** hides it.

- The suggestions follow the server's version, from 1.13 up to 26.x, so a
  1.21.10 server is offered `keepInventory` and a 26.3 server
  `keep_inventory`. The version is read from the server's start-up line,
  its status ping or the jar's name.
- Player names come from the Players tab (online players first), and the
  game's own rules apply: `pardon` offers banned players, `deop` offers
  operators, `whitelist remove` offers whitelisted players.
- Only vanilla commands are known. Commands added by plugins or mods are
  still sent as typed, they just get no suggestions. Bedrock servers and
  proxies (Velocity, BungeeCord) get none.
- When a new Minecraft version comes out, `dev/command-data/generate.py`
  builds its data file from the game's own command list (see the top of
  that file for how to run it).

![Command suggestions in the Better Crafty terminal](docs/screenshots/terminal-complete-after.png)

### Config

Settings are grouped into General, Game settings, Startup, Status checks, and
Crashes and shutdown. **Game settings** edits common `server.properties`
values (message of the day, max players, game mode, difficulty, PvP,
whitelist, view distance and more) and only rewrites the lines you changed.
**Memory** has minimum and maximum fields instead of `-Xms` / `-Xmx` in the
start command. The save bar stays on screen, the page warns before you leave
with unsaved changes, and deleting the server is in a separate danger zone.

| Before | After |
|---|---|
| ![Config tab in Crafty 4.11.0](docs/screenshots/config-before.png) | ![Config tab in Better Crafty](docs/screenshots/config-after.png) |

### Players

Every player who has ever joined the server is listed, not just the ones
online now, with their play time and when they last played. Search the list
by name or UUID. The whitelist, operators and banned players are read from
the game's own files. Add or remove someone with one click; the command goes
to the server console for you. The page also tells you when the whitelist is
turned off, so anyone can join.

| Before | After |
|---|---|
| ![Player management in Crafty 4.11.0](docs/screenshots/players-before.png) | ![Player management in Better Crafty](docs/screenshots/players-after.png) |

**Details** opens a window for one player (Minecraft Java servers):

- **Overview:** health, hunger, level, game mode, where they are, their
  spawn point and where they last died. Kick, ban, op, whitelist or change
  their game mode from here.
- **Inventory:** armor, off hand, main inventory and hotbar laid out like the
  game. Click an item for its enchantments, durability, custom name and
  what is inside shulker boxes and bundles. Hover an item for a game-style
  tooltip.
- **Ender chest**, **Statistics** (play time, deaths, kills, distance, most
  mined, crafted and killed, and every other statistic in a searchable
  table) and **Advancements**.

**Item pictures** are optional. Minecraft's item art belongs to Mojang, so
Better Crafty does not ship it. The first time, a super user presses
**Show item pictures**: Crafty downloads the newest Minecraft client from
Mojang once (about 40 MB, checked against Mojang's checksum), draws a
picture of every item into `app/config/item_icons/` and deletes the
download. After that the inventory, ender chest and statistics show the
items as in the game, with enchantment shine. The inventory then looks like
the game's own screen: the player's skin turns to follow your mouse, the
empty crafting grid sits beside it, and the experience level, hearts and
food are below it. Players with a Minecraft account get their own skin from
Mojang (kept for a few hours); offline-mode players get the default skin the
game would give them. Without the pictures, items are shown by name. A few
items the game draws with special code (banners, decorated pots, dragon and
piglin heads, copper golem statues) still show their name; player heads in
the inventory show Steve's face.

All of this is read from the world's save files, so nothing is changed and
it works while the server is stopped. The game saves player data every few
minutes; while the server is running, **Save now** asks it to save straight
away. Save files from Minecraft 1.12 up to the newest format are understood.

| Inventory | Statistics |
|---|---|
| ![A player's inventory in Better Crafty](docs/screenshots/player-inventory-after.png) | ![A player's statistics in Better Crafty](docs/screenshots/player-stats-after.png) |

### Backups

Each backup plan shows its last backup (when, and how big), how many copies
it keeps and its type, and the buttons say what they do ("Back up now",
"Restore or download").

| Before | After |
|---|---|
| ![Backups tab in Crafty 4.11.0](docs/screenshots/backups-before.png) | ![Backups tab in Better Crafty](docs/screenshots/backups-after.png) |

### File manager

Click any folder in the path to go back to it. Files show a readable type
("Folder", "Text file", "Java archive") and every row has a ⋮ button that
opens the same menu as a right-click (handy on phones and with a keyboard).

| Before | After |
|---|---|
| ![File manager in Crafty 4.11.0](docs/screenshots/files-before.png) | ![File manager in Better Crafty](docs/screenshots/files-after.png) |

### Metrics

CPU, memory and online players each get their own chart. Zooming or dragging
one chart moves the others too, and quick buttons pick a time range (last
hour, day, week and so on).

| Before | After |
|---|---|
| ![Metrics tab in Crafty 4.11.0](docs/screenshots/metrics-before.png) | ![Metrics tab in Better Crafty](docs/screenshots/metrics-after.png) |

### Logs

The filter is at the top, hidden words show as chips you can remove, and the
page says how many lines are hidden. "Live terminal" jumps to the Terminal,
and the Terminal has an "Older logs" button back.

| Before | After |
|---|---|
| ![Logs tab in Crafty 4.11.0](docs/screenshots/logs-before.png) | ![Logs tab in Better Crafty](docs/screenshots/logs-after.png) |

### On a phone

The server header shrinks to the status, buttons and four numbers ("More
details" shows the rest). File details move under the file name instead of
being cut off.

| | Before | After |
|---|---|---|
| **Login** | <img src="docs/screenshots/login-phone-before.jpg" width="220" alt="Phone login in Crafty 4.11.0"> | <img src="docs/screenshots/login-phone-after.jpg" width="220" alt="Phone login in Better Crafty"> |
| **Server** | <img src="docs/screenshots/terminal-phone-before.png" width="220" alt="Phone server page in Crafty 4.11.0"> | <img src="docs/screenshots/terminal-phone-after.png" width="220" alt="Phone server page in Better Crafty"> |
| **Files** | <img src="docs/screenshots/files-phone-before.png" width="220" alt="Phone file manager in Crafty 4.11.0"> | <img src="docs/screenshots/files-phone-after.png" width="220" alt="Phone file manager in Better Crafty"> |

## Bug fixes

Things that were broken in Crafty 4.11.0 and work in Better Crafty:

**Login and accounts**

- After too many failed logins, the login kept checking the password anyway,
  and a wrong backup code did not stop the login either.
- Logging out without being logged in showed an error page.
- Deleting your last passkey left the account with no way to log in.
- Creating a user without a password failed without saying why.
- The "require two-factor" option was read wrongly when creating a role.

**Servers**

- The EULA check could misread `eula.txt`.
- Killing a server did not update pages that were already open.
- Port checks used the wrong setting and accepted invalid ports.
- In the new server forms, versions like `1.20` were turned into the number
  `1.2`, and the create button could be pressed twice.
- Schedule and webhook on/off switches got stuck after one click.
- A failed backup restore left the loading spinner on screen forever.
- Pressing Ctrl+S quickly in the file editor sent several saves and showed a
  false "file was changed" warning.
- Files with `%`, `#` or `&` in their name opened the wrong file in the
  editor, and uploading files with non-Latin names (Greek, emoji) failed.
- Files added by "load more" in the file manager could not be clicked.
- The schedules list endpoint crashed (error 500).

**Everywhere else**

- Dashboard buttons on phones did not update, player totals could break,
  and the CPU and memory warning colours used the wrong limits.
- Notifications showed up twice and the bell made the page jump.
- Pages crashed when the live connection (websocket) was not available.
- Several forms reported success when the save had failed, or showed nothing
  when it failed.

## Security fixes

- **Code in names (stored XSS).** File, folder and player names were put
  into the page as HTML, so a file named like a piece of script could run
  code in the browser of anyone who opened the file manager or a backup
  dialog. Names are now shown as plain text.
- **Other servers' data (IDOR).** Schedules, webhooks and backups were
  looked up by their ID only, so a user with access to one server could
  read or change another server's items by putting their ID in the address.
  They now have to belong to the server in the address.
- **Redirect after login.** A login link could send people to another
  website after they logged in. It now only goes to pages on the panel.
- **Requests from other websites (CSRF).** The login cookie had no
  `SameSite` setting and the API does not check where requests come from,
  so in some browsers a website you visit while logged in could secretly
  send commands to your panel. The cookie is now `SameSite=Lax`, which
  tells the browser to send it only from the panel's own pages. (If you
  show Crafty inside a frame on another website, that frame will no longer
  stay logged in.)

## Install

Better Crafty runs on Linux, on `amd64` or `arm64` computers (for example a
Raspberry Pi 4 or 5 with a 64-bit system). The easiest way is the ready-made
Docker image on Docker Hub,
[`giorgospap777/better-crafty`](https://hub.docker.com/r/giorgospap777/better-crafty).
The official Crafty images (`registry.gitlab.com/crafty-controller/crafty-4`
and `arcadiatechnology/crafty-4`) are plain Crafty and do **not** include
these changes. There is no Windows build.

### Docker Compose (recommended)

Make a folder for Better Crafty and save this in it as `docker-compose.yml`:

```yaml
services:
  crafty:
    container_name: crafty_container
    image: giorgospap777/better-crafty:latest
    restart: always
    environment:
      - TZ=Etc/UTC
    ports:
      - "8443:8443" # the panel (HTTPS)
      - "8000:8000" # HTTP
      - "25500-25600:25500-25600" # Minecraft Java servers
      - "19132:19132/udp" # Bedrock
      - "8123:8123" # Dynmap
      - "5520-5550:5520-5550/udp" # Hytale
    volumes:
      - ./backups:/crafty/backups
      - ./logs:/crafty/logs
      - ./servers:/crafty/servers
      - ./config:/crafty/app/config
      - ./import:/crafty/import
```

Set `TZ` to your time zone (for example `Europe/Athens`) so that backups,
schedules and logs use your local time. Then, in that folder:

```sh
docker compose up -d
docker compose logs -f      # wait for "Crafty has fully started", then Ctrl+C
sudo cat config/default-creds.txt
```

On the first start Crafty creates an `admin` user and writes its password to
`config/default-creds.txt`. Open `https://<your-server>:8443`, accept the
browser's warning about the self-signed certificate, log in as `admin` with
that password, and change the password.

Your servers, backups, logs and settings live in the folders next to
`docker-compose.yml`, not inside the container, so updating or recreating the
container keeps them.

### docker run

The same without Compose, from the folder where the data should live:

```sh
docker run \
  --name crafty_container \
  --detach \
  --restart always \
  -p 8443:8443 \
  -p 8000:8000 \
  -p 25500-25600:25500-25600 \
  -p 19132:19132/udp \
  -p 8123:8123 \
  -p 5520-5550:5520-5550/udp \
  -e TZ=Etc/UTC \
  -v "$(pwd)/backups:/crafty/backups" \
  -v "$(pwd)/logs:/crafty/logs" \
  -v "$(pwd)/servers:/crafty/servers" \
  -v "$(pwd)/config:/crafty/app/config" \
  -v "$(pwd)/import:/crafty/import" \
  giorgospap777/better-crafty:latest
```

The ports are: 8443 (panel, HTTPS), 8000 (HTTP), 25500-25600 (Minecraft Java
servers), 19132/udp (Bedrock), 8123 (Dynmap), 5520-5550/udp (Hytale). Leave
out the ones you do not need.

### Image tags

| Tag | What it is |
|---|---|
| `latest` | The newest release. Use this one. |
| `1.0.0`, `1.0`, ... | A fixed release, if you want to choose when to move to a newer one. |
| `edge` | The newest code, built after every change. Less tested; for trying things out. |

### Off-site backups in Docker

For off-site backups to another disk or a network share, mount it into the
container too, for example `- /mnt/backupdisk:/crafty/offsite` under
`volumes:` (or `-v /mnt/backupdisk:/crafty/offsite` with `docker run`), and
use `/crafty/offsite` as the folder in Panel Config → Off-site storage. Cloud
storage needs no mount.

> **Docker on Windows (WSL / WSL2 / Docker Desktop):** the Crafty team warns
> that stopping or restarting a Minecraft server there can corrupt the
> world. Run Docker on Linux.

### Build the image yourself

```sh
git clone https://github.com/GiorgosPap777/Better-Crafty.git
cd Better-Crafty/docker
docker compose up -d --build
```

`docker/docker-compose.yml` builds the image from this repository and keeps
your data in the `docker/` folder. The first build takes several minutes.

### Without Docker (Linux)

Needs Python 3.10 or newer and the Java version your Minecraft servers need.
Crafty will not run as `root`, so use a normal user.

```sh
git clone https://github.com/GiorgosPap777/Better-Crafty.git
cd Better-Crafty
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

The `admin` password is in `app/config/default-creds.txt`.

## Updating

The panel tells you when a new Better Crafty release is out. Back up the
`config` folder first; Crafty updates its database by itself on the first
start of the new version.

- **Docker Compose:** in the folder with `docker-compose.yml`, run
  `docker compose pull` and then `docker compose up -d`.
- **docker run:** `docker pull giorgospap777/better-crafty:latest`, then
  `docker stop crafty_container` and `docker rm crafty_container` (your data
  is in the mounted folders), then the same `docker run` command as before.
- **Built yourself:** `git pull`, then `docker compose up -d --build`.
- **Without Docker:** stop Crafty, then `git pull`,
  `.venv/bin/pip install -r requirements.txt`, and start it again.

## Moving from Crafty Controller

Better Crafty uses the same database and folders as Crafty, so everything
carries over: users and their passwords, roles, servers, schedules, backups
and settings. It adds one table and three columns for off-site backups,
which the original Crafty ignores, so you can also go back. Both ways were
tested with Docker and with a Linux install set up the way Crafty's installer
does it.

**Which Crafty version:** Better Crafty is based on Crafty 4.11.0, the newest
release when this was written.

- From 4.11.0: it simply takes over.
- From an older 4.x version: Crafty's own database upgrade runs on the first
  start, as it would when updating Crafty. After that, going back needs Crafty
  4.11.0 or your backup.
- From a version newer than 4.11.0: wait until Better Crafty catches up.

**Back up first:** at least the `config` folder (Docker) or `app/config`
(Linux). It holds the database, the users and the settings.

### With Docker

1. In the folder with `docker-compose.yml`: `docker compose down`.
2. Back up: `sudo cp -a config config-backup`.
3. In `docker-compose.yml`, change only the `image:` line to
   `image: giorgospap777/better-crafty:latest`. Keep the volumes as they are.
4. `docker compose pull`, then `docker compose up -d`.

Log in with your usual account. With `docker run`: `docker stop` and
`docker rm` the old container, then run the same command with
`giorgospap777/better-crafty:latest` as the image.

### With Crafty's Linux installer

The installer puts Crafty in `/var/opt/minecraft/crafty/crafty-4` (use your
folder if you chose another one). Switch the code **in place**: Crafty stores
each server's full path in its database, so do not install into a new folder
and copy the data across.

```sh
sudo systemctl stop crafty
sudo cp -a /var/opt/minecraft/crafty/crafty-4/app/config ~/crafty-config-backup
cd /var/opt/minecraft/crafty/crafty-4
sudo -u crafty git remote rename origin crafty-original
sudo -u crafty git remote add origin https://github.com/GiorgosPap777/Better-Crafty.git
sudo -u crafty git fetch origin
sudo -u crafty git remote set-head origin --auto
sudo -u crafty git checkout -b better-crafty --track origin/HEAD
sudo -u crafty ../.venv/bin/pip install -r requirements.txt
sudo systemctl start crafty
```

- The installer's `run_crafty.sh` and `crafty.service` keep working.
- **Do not use the installer's `update_crafty.sh` afterwards.** It is written
  for the original Crafty's `master` branch. To update Better Crafty:
  stop Crafty, then `sudo -u crafty git pull` and
  `sudo -u crafty ../.venv/bin/pip install -r requirements.txt` in the
  `crafty-4` folder, and start it again.
- If `git checkout` complains about local changes, files were edited by
  hand; run `sudo -u crafty git stash` first.

### Going back to the original Crafty

- **Docker:** put the old `image:` line back
  (`arcadiatechnology/crafty-4:latest` or
  `registry.gitlab.com/crafty-controller/crafty-4:latest`), then
  `docker compose pull` and `docker compose up -d`.
- **Linux installer:** stop Crafty, then in the `crafty-4` folder
  `sudo -u crafty git checkout master` (or `dev`, whichever you used before)
  and `sudo -u crafty ../.venv/bin/pip install -r requirements.txt`, and start
  it again.

Off-site copies stop while the original Crafty runs; their settings are kept
for when you come back.

## Credits and license

Crafty Controller is made by Arcadia Technology and the Crafty community.
All credit for the program itself goes to them; this fork only changes parts
of it.

- Crafty homepage: https://craftycontrol.com
- Crafty documentation: https://docs.craftycontrol.com (still applies to
  this fork)
- Crafty source code: https://gitlab.com/crafty-controller/crafty-4
- Crafty Discord: https://discord.gg/9VJPhCE (for Crafty itself, not for
  this fork)

Better Crafty is released under the same license as Crafty Controller, the
[GNU General Public License v3.0](LICENSE).
