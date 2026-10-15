[![Crafty Logo](app/frontend/static/assets/images/logo_long.svg)](https://craftycontrol.com)

# Better Crafty

> A fork of [Crafty Controller](https://craftycontrol.com) 4.11.0 with a reworked
> login screen, easier server management pages and a long list of bug and
> security fixes.

Crafty Controller is a web control panel for Minecraft servers: it runs your
servers in the background and gives you a website to start, stop, configure
and back them up. **Better Crafty is the same program**, with changes to the
parts people use every day. It reads the same folders and database as Crafty
4.11.0 (no database changes), so it can take over an existing install.

This fork is not made by or affiliated with the Crafty Controller team.
Please report problems with this fork here, not to them.

**Contents:** [What changed](#what-changed) ·
[Before and after screenshots](#before-and-after) ·
[Bug fixes](#bug-fixes) · [Security fixes](#security-fixes) ·
[Install](#install) · [Credits and license](#credits-and-license)

## What changed

| Area | In short |
|---|---|
| **Login** | Rebuilt page: a separate two-factor step, show password, a countdown after too many failed tries, several login bugs fixed. |
| **Server page header** | The same header on every server tab: status, Start / Restart / Stop, live uptime, CPU, memory, players and version. |
| **Terminal** | Command suggestions like the game's chat box (press Tab), auto-scroll switch, command history with the ↑ and ↓ keys, a cap of 2,000 lines so the page stays fast, a link to older logs. |
| **Config** | Split into sections. Game settings (`server.properties`) and memory are normal form fields now, so no more editing the file or the Java command by hand. |
| **Players** | Everyone who has ever joined, with play time and last seen. Each player opens to their inventory, armor, ender chest, statistics and advancements. Whitelist, operators and bans in one place. |
| **Backups** | Shows the last backup (time and size) and how many copies are kept. Buttons have labels. Restore errors are shown, and restoring a snapshot asks first. |
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
  what is inside shulker boxes and bundles.
- **Ender chest**, **Statistics** (play time, deaths, kills, distance, most
  mined, crafted and killed, and every other statistic in a searchable
  table) and **Advancements**.

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

There are no ready-made images or Windows builds for this fork yet, so you
build it from this repository. The official images
(`registry.gitlab.com/crafty-controller/crafty-4` and
`arcadiatechnology/crafty-4`) are plain Crafty and do **not** include these
changes.

On first start Crafty creates an `admin` user and writes its password to
`app/config/default-creds.txt` (in Docker: `docker/config/default-creds.txt`).
The panel is at `https://<your-server>:8443`.

### Docker Compose (recommended)

```sh
git clone https://github.com/GiorgosPap777/Better-Crafty.git
cd Better-Crafty/docker
docker compose up -d --build
docker compose logs -f
```

`docker/docker-compose.yml` builds the image from this repository and keeps
your servers, backups, logs and settings in the `docker/` folder. To update
later: `git pull`, then run `docker compose up -d --build` again.

### docker run

```sh
git clone https://github.com/GiorgosPap777/Better-Crafty.git
cd Better-Crafty
docker build . -t better-crafty

docker run \
	--name crafty_container \
	--detach \
	--restart always \
	-p 5520-5550:5520-5550/udp \
	-p 8000:8000 \
	-p 8443:8443 \
	-p 8123:8123 \
	-p 19132:19132/udp \
	-p 25500-25600:25500-25600 \
	-e TZ=Etc/UTC \
	-v "/$(pwd)/docker/backups:/crafty/backups" \
	-v "/$(pwd)/docker/logs:/crafty/logs" \
	-v "/$(pwd)/docker/servers:/crafty/servers" \
	-v "/$(pwd)/docker/config:/crafty/app/config" \
	-v "/$(pwd)/docker/import:/crafty/import" \
	better-crafty
```

The ports are: 8443 (panel, HTTPS), 8000 (HTTP), 25500-25600 (Minecraft Java
servers), 19132/udp (Bedrock), 8123 (Dynmap), 5520-5550/udp (Hytale).

The first build takes several minutes; later builds are quick. The image
works on `amd64` and `arm64`.

> **Docker on Windows (WSL / WSL2 / Docker Desktop):** the Crafty team warns
> that stopping or restarting a Minecraft server there can corrupt the
> world. Run Docker on Linux, or run Crafty directly on Windows.

### Without Docker (Linux)

Needs Python 3.9 or newer and Java for your Minecraft servers. Crafty will
not run as `root`, so use a normal user.

```sh
git clone https://github.com/GiorgosPap777/Better-Crafty.git
cd Better-Crafty
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

### Moving over from Crafty 4.11.0

Better Crafty uses the same database and folders, so you can point it at
your existing `config`, `servers`, `backups` and `logs` folders (in Docker,
mount the same volumes). Back them up first, just in case.

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
