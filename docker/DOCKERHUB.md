# Better Crafty

A fork of [Crafty Controller](https://craftycontrol.com) 4.11.0, the web
control panel for Minecraft servers, with a reworked login screen, easier
server management pages and a long list of bug and security fixes.

![A Minecraft server's Terminal in Better Crafty](https://raw.githubusercontent.com/GiorgosPap777/Better-Crafty/HEAD/docs/screenshots/terminal-after.png)

- **Server pages:** the same header on every tab (status, Start / Restart /
  Stop, CPU, memory, players), and restarts that warn the players in the
  game first, also from schedules.
- **Terminal:** command suggestions like the game's chat box, command history.
- **Config:** `server.properties` and memory as normal form fields.
- **Players:** everyone who has joined, with their inventory, ender chest,
  statistics and advancements; whitelist, operators and bans in one place.
- **Backups:** a clearer page, plus copies to another disk, a network share
  or S3-compatible cloud storage (AWS S3, Backblaze B2, Cloudflare R2, MinIO).
- **World:** download the world as a zip, reset the Nether or the End.
- Files, metrics, logs and phone layouts reworked, and many fixes.

Screenshots and the full list: [GitHub](https://github.com/GiorgosPap777/Better-Crafty).
This fork is not made by or affiliated with the Crafty Controller team.

## Quick start

`docker-compose.yml`:

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

```sh
docker compose up -d
sudo cat config/default-creds.txt
```

Open `https://<your-server>:8443`, accept the warning about the self-signed
certificate, and log in as `admin` with the password from
`config/default-creds.txt`. Set `TZ` to your time zone (for example
`Europe/Athens`).

## Tags

| Tag | What it is |
|---|---|
| `latest` | The newest release. Use this one. |
| `1.0.0`, `1.0`, ... | A fixed release. |
| `edge` | The newest code, built after every change. Less tested. |

Built for `linux/amd64` and `linux/arm64` (for example a Raspberry Pi 4 or 5
with a 64-bit system).

## Folders

| In the container | Holds |
|---|---|
| `/crafty/app/config` | The database, users and settings |
| `/crafty/servers` | Your Minecraft servers |
| `/crafty/backups` | Backups |
| `/crafty/logs` | Crafty's logs |
| `/crafty/import` | Files to import servers from |

For off-site backups to another disk or a network share, mount it too (for
example `/mnt/backupdisk:/crafty/offsite`) and choose `/crafty/offsite` in
Panel Config → Off-site storage.

## Updating

`docker compose pull`, then `docker compose up -d`. Your data stays in the
mounted folders.

## Moving from Crafty Controller

Better Crafty uses the same database and folders as Crafty 4.11.0: stop
Crafty, back up the `config` folder, change only the `image:` line to
`giorgospap777/better-crafty:latest`, then `docker compose pull` and
`docker compose up -d`. Users, servers, schedules and backups carry over, and
you can go back the same way. Details, older versions and the Linux
installer: [Moving from Crafty Controller](https://github.com/GiorgosPap777/Better-Crafty#moving-from-crafty-controller).

## License

GNU General Public License v3.0, the same as Crafty Controller.
[Source code and issues on GitHub](https://github.com/GiorgosPap777/Better-Crafty).
