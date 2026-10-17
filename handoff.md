# Better Crafty: handoff notes

This file is the project's memory. Sessions 1-11 ran in temporary cloud
containers, so only what is committed survives. It records what has been
done, what is unfinished, and how to set up and test on any machine. Keep it
up to date: add the owner's request, a section per session, and a row in the
commits table.

## Start here

**State (2026-10-17, session 12 in progress):** see "Session 12" for what
is done and what is next. The owner approved a list of suggestions (update
check, tests on GitHub, versions, upstream, error pop-ups, then bigger
features) and is setting up Docker Hub themselves; they will say when to
check it. Items 1 to 5 are done, plus a fix for an upstream bug that made
saves fail with "database is locked". Of the bigger features, the restart
with in-game warnings is done; world tools are next. The GitHub Actions
runs pass and already publish `edge` to Docker Hub (the owner's secrets
are set). Session 11 added the player's skin and the game's HUD layout to
the inventory, and reviewed the whole fork for serious bugs (four found and
fixed). The owner has not yet said which special items (banners, pots,
dragon/piglin heads, copper golem statues) they want drawn.
Done before: login, server pages, security fixes, README with screenshots,
player management (session 7), command suggestions in the Terminal
(session 8), portable test tools (session 9), and item pictures with a
game-style inventory (session 10).
**Also unfinished: session 6** (test the Docker image, publish it, and
write the install, update and migration docs). The owner said they would
pick that up later. The owner works in cloud sessions; the steps below work
on any machine.

1. **Get the code.** `git clone https://github.com/GiorgosPap777/Better-Crafty.git`.
   The working branch `claude/login-server-admin-improvements-ctbqdu` is the
   repo default, so a fresh clone is already on it. In an existing clone:
   `git fetch origin && git checkout claude/login-server-admin-improvements-ctbqdu && git pull`.
2. **Set up and check** with "Development setup" below (about 10 minutes).
   You should see 193 passing pytest tests before changing anything.
3. **Ask the owner what to work on next.** If it is the Docker work, follow
   "Session 6" from "Next steps, in order". It needs two answers from them:
   their Docker Hub username, and whether to publish to Docker Hub only or
   also to GitHub's registry (`ghcr.io`).
4. Before you finish, update this file, commit and push (see "The project").

### How the owner likes to work

- Short, plain status updates and reports.
- **Subagents use far more of their usage than they expected: use them
  sparingly.** (They once allowed Haiku subagents; prefer doing the work
  yourself.)
- Ask when something is genuinely theirs to decide; otherwise pick the
  sensible option and say so.
- Never ask them to paste a password or token into the chat. For Docker Hub
  they run `docker login` themselves, or add repo secrets on GitHub.
- Don't put machine details (proxy addresses, environment values, local
  paths) into screenshots, the README or other committed files.

## The project

- A fork of **Crafty Controller 4.11.0** (Python Tornado + peewee/SQLite;
  jQuery + Bootstrap 4.3.1 + bootbox front end; Phosphor icons).
- Repo: `giorgospap777/better-crafty`. **All work is on branch
  `claude/login-server-admin-improvements-ctbqdu`.** It is the only branch
  on GitHub and the repo default, so the README shows on the front page.
- Push with `git push -u origin claude/login-server-admin-improvements-ctbqdu`.
  Do **not** open a PR unless the owner explicitly asks.
- Commit messages end with the attribution lines the session supplies.

### What the owner asked for (in their words)

1. "Fork crafty controller, and let's make some improvements. First, make the
   login screen a bit better because it is a bit buggy."
2. "Secondly, make the server administration and everything in the UI in
   general better. Then we will continue on from there. If you have any
   questions or problems, ask me."
3. "If you need to you can use haiku 5.5 subagents."
4. Asked for this handoff file because they were near their usage limit.
5. Session 2: the login felt "really buggy" in general (no single bug to
   name). "Don't do too much in this run." Asked for screenshots of every
   server management page so they could suggest changes, and said
   **subagents use far more usage than expected, so use them sparingly.**
6. Session 3: "Everything looks good. And the suggestions you said were more
   than I have thought, and they are really good, we might as well so get
   started." So the suggestions listed under Session 3 below were approved
   and built.
7. Session 5: asked what the SameSite risk was ("I didn't understand it"),
   said they don't embed Crafty in other sites, and asked for a README "in
   such a way so that if another person other than me goes to the repo
   understands what the changes are", with images. Done (see Session 5).
8. Session 6: "Now that I see it, the readme.md has not been changed. Could
   you also make a Docker image and publish it to Docker Hub? If you cannot
   create a new repo on Docker Hub, tell me. also have instructions on how
   to properly install it and run it, and how to migrate from the original
   Crafty controller." **Half done, see Session 6.**
9. Then moved the work to an agent on their own PC, because the cloud
   session lacked the tools they normally use, and asked for this handoff.
10. Session 7: "Ok I will do that later can you work on player management
    ( inventorys , statistics etc)". Done, see Session 7.
11. Session 8: "Could we implement a auto complison in the command like
    like in the game". Done, see Session 8.
12. Session 9: "Ok can we do the handoff.md thing now. Make sure that the
    new agent will be able to continue on no problem". Done: this file,
    `CLAUDE.md`, and test tools that work on any machine (see Session 9).
13. Session 10: "Ok I changed my mind let's iderete like this no need to
    move. Could we have the player management have the icem icon and the
    inv ui". So: keep working in cloud sessions, and show item pictures
    and an inventory like the game's. Done, see Session 10.
14. Session 11: "Okay, I thought about something we could do. Where you see
    the inventory of this of the player, could we move the health below the
    inventory on the left, the food below the inventory on the right, and
    the levels below the inventory above the health and the food, like it is
    on the real game? And if possible, could we have the skin of the player
    be visible? Also, make sure that there is not any catastrophic bugs or
    something, because I want to run my server with this." HUD and skin
    done; **bug review half done**, see Session 11.
15. Session 11, later: "Also, why do banners, decorated pots, dragon, piglin
    heads, copper golem statues and all of that cannot be shown as an
    image?" Answered in chat (see Session 11). Then the owner hit their
    usage limit, asked for this file to be brought up to date, and told
    the session to stop.
16. Session 11, next day: "ok finish what you were doing now". Done: the
    config page fix checked in a browser, the rest of the review, README.
17. Session 12: "Okay, now tell me if you have any suggestions, and also
    what do I need to do to also publish the image in Docker Hub to be
    easier to deploy." Answered in chat: Docker Hub steps (account, access
    token, two GitHub repo secrets, tell us the username) and a list of
    suggestions (see Session 12).
18. Session 12: "Okay, the suggestions you said are awesome. So, can we
    start doing them? I will do the Docker thing you mentioned in parallel,
    and when I'm done, I will tell you to check it." See Session 12.

### Questions still waiting on the owner

- Should a PR to `main` be opened? (Explained what it means; not opened.)
- Session 6: publish to Docker Hub only, or also to GitHub's registry
  (`ghcr.io`)? They only asked for Docker Hub. And what is their Docker Hub
  username (needed for the image name in the README)? Never ask them to
  paste a password or token into the chat.
- (Answered in session 5.) The token cookie is now `SameSite=Lax`
  (`api/auth/login.py`, `api/auth/passkey.py`): the API turns XSRF checks
  off, so without it another site could call the API as the logged-in user.
  The owner does not embed Crafty in iframes on other sites, which is the
  one thing this breaks.
- `show_errors` defaults to true, so tracebacks reach the browser. Upstream
  choice.

## Commits so far

| Commit | What |
|---|---|
| `d3946c3f` | Login screen fixes and redesign |
| `360b0f92` | Server administration pages (shared server header, console) |
| `bc6fb12b` | UI pass 2: fixes across dashboard, settings, users, wizards, plus this handoff |
| `134253cf` | Handoff notes: screenshot review findings |
| `a353b966` | Stored XSS in file/backup pages, file manager bugs, JSON replacers |
| `e909ed94` | IDOR: schedules/webhooks/backups checked against the server; schedules API 500s |
| `a80352ca` | Config tab: game settings (server.properties) editor, memory fields, sections |
| `a65d5550` | Players tab: whitelist, operators, bans, names as text |
| `62f7e098` | Backups tab: last backup, copies kept, labelled actions |
| `386c539f` | File manager: readable types, path bar, phone actions |
| `7027dda7` | Metrics: CPU, memory, players charts; quick time ranges |
| `54455760` | Compact server header on phones |
| `c44b0f88` | Logs tab: filter above the log, empty state, link with Terminal |
| `1b91543a` | On/off switches, restore errors, snapshot confirm, editor double save |
| `e409e2fc` | Handoff notes for sessions 2-4, test scripts |
| `0374b193` | Login cookie `SameSite=Lax` |
| `8806e7ec` | README for visitors with before/after screenshots |
| `4e9e1244` | Dockerfile `ARG TARGETARCH` fix and fork labels; draft publish workflow; this handoff (session 6) |
| `b1e8df99` | Player management: every player, details window (inventory, ender chest, stats, advancements) (session 7) |
| `91fa95ee` | Terminal command suggestions like the game's chat box (session 8) |
| `3363122c` | Handoff for the owner's PC: `CLAUDE.md`, portable test tools, test data setup, role page fix (session 9) |
| `6ee33fd2` | Item pictures drawn from the Minecraft game; inventory, ender chest and tooltips like the game's (session 10) |
| `423d2a9c` | Player skin in the inventory; hearts, food and XP below the inventory like the game; 2x2 crafting grid (session 11) |
| `46684a64` | Bug-review fixes: safe `server.properties` writes, trailing backslash, memory flags, config memory boxes (session 11) |
| `3d3158b2` | End of the review: odd memory sizes in `test_config.js`, README skin and HUD, this handoff (session 11) |
| `57ed1545` | Update check reads this fork's GitHub releases; Better Crafty version; tests and Docker publish on GitHub Actions (session 12) |
| `7bbdc549` | Error pop-ups show the server's text as text; fix for "database is locked" after opening a backup's settings (session 12) |
| `5a900db6` | Restart with in-game warnings: panel menu, countdown with Cancel, schedules (session 12) |
| (this commit) | Players tab reads the new player folders of Minecraft 26.1 and newer (session 12) |

### 1. Login (`d3946c3f`)

- `app/classes/web/routes/api/auth/login.py`: missing `return` after the 429
  cooldown and after a backup-code error (both fell through and kept running);
  returns `MFA_REQUIRED` (401) when the password is right but a TOTP code is
  needed, so the page can show a 2FA step; translated "account disabled".
- `app/classes/web/public_handler.py`: `safe_next_url()` blocks open
  redirects via `?next=`; `/logout` with no session no longer errors;
  logged-in users visiting `/login` go to the dashboard; passes
  `passkey_enabled` to the page.
- `app/frontend/templates/public/login.html` +
  `static/assets/css/partial/crafty-login_page.css`: rewritten page with a
  2FA step, show/hide password, cooldown countdown, forgot-password
  confirmation, `next` redirect, passkeys.
- Tests: `tests/classes/web/test_public_handler.py`.

### 2. Server administration (`360b0f92`)

- `panel/parts/details_stats.html`: one shared server header for all server
  tabs (`serverOverview` IIFE): live stats via `/stats` API, start/stop/
  restart/kill with pending states, kill confirmation, "updating" state.
  `panel/parts/server_title.html`, `css/partial/crafty-server-overview.css`
  (includes `.btn-ghost`).
- `panel/server_term.html` + `css/partial/crafty-terminal.css`: console
  toolbar, command history (up/down), 2000-line cap, jump-to-bottom button,
  focus without scrolling the page.
- `app/classes/models/server_stats.py`: memory shown human-readable
  (`mem_raw` kept for maths).
- `app/classes/shared/server.py`: **EULA bug** fixed: new
  `is_eula_accepted(eula_path)` (the old readline check could misread the
  file). Kill now also removes the `save_stats` job.
- `app/classes/shared/tasks.py`: kill now broadcasts `send_start_reload`, so
  open pages update (before, they never noticed).
- Tests: `tests/classes/shared/test_eula.py`.

### 3. UI pass 2 (`bc6fb12b`)

Back end:
- `api/roles/index.py`: role creation passed `mfa_required` wrongly; now
  `data.get("mfa_required", False)`.
- `api/servers/index.py`: port check used the wrong key and default; now
  reads `{monitoring_type}_monitoring_data.port`, defaults 25565 / 19132, and
  rejects non-int or out-of-range ports.
- `controllers/passkey_controller.py`: deleting your last passkey now turns
  password login back on (otherwise the user was locked out). Tests:
  `tests/classes/shared/test_passkey_delete.py`.

Dashboard (`panel/dashboard.html`, `css/crafty.css`):
- Sideways-scroll hint for the server table at 576–1000px widths
  (remembered in localStorage).
- Mobile action buttons got their own ids (`m_controls{id}`) and are updated
  along with desktop ones; CSS specificity fix so they render as buttons.
- Fixed broken `</h4>`, server description span always present, memory
  tooltips use `total_mem`, new `update_player_totals()` (null-safe),
  player counts use `pinged`, command send has error handling + XSRF header,
  "stop all" catches errors, threshold colours (`<= 66`, `<= 75`) fixed.

Everywhere else:
- `base.html`: no crash when the websocket is unavailable (HTTP); removed the
  dead announcements dropdown code; support-log progress bar guard.
- `notify.html`: no duplicate notifications or click handlers on re-render;
  polling survives errors; bell no longer jumps the page; aria-label
  (new `notify.announcements` key in `en_EN.json`).
- Server wizards (`server/*.html`): JSON replacers no longer turn names like
  `"1.20"` into numbers; bedrock modal id fix; EULA dialogs check the form is
  valid first; steam default option; Java `mem_min`/`mem_max` selectors;
  `send_server` rewritten to block double submits and report errors; port
  `max="65535"`.
- Users/roles/settings: OTP page button disabling and alert timing;
  backup-code renew icon works from settings (`backupCodes.js` handles
  `.renew-codes` with a `data-id`); new user without password now asks for
  one instead of failing silently; role name replacer fix; `config_json`
  replacer no longer mangles arrays; spinners reset on error; API-key name
  escaped in the confirm dialog.
- Small: `server_webhooks.html` table toggle, `denied.html` dead JS,
  `blank_base.html` duplicate script, `server_file_edit.html` title.

## Sessions 2-4

Everything the first audit listed (XSS, file manager bugs, JSON replacers,
false success messages, websocket crash, double submits, port max) and every
bug found in the session 2 screenshots is now fixed. Commit messages above
have the details; the notes below are what is useful when changing the code.

### Security fixes

- `a353b966`: file and folder names were put into `innerHTML` unescaped
  (stored XSS). New `escapeHtml()` in `static/assets/js/shared/misc.js`
  (loaded on every page via `base.html` and `blank_base.html`). Use it for
  any value built into HTML strings, including bootbox titles/messages
  (bootbox treats them as HTML).
- `e909ed94`: schedule, webhook and backup endpoints and edit pages loaded
  items by id without checking the server in the URL (IDOR). They now 404.
- `a65d5550`: player names from the status ping were HTML / inline onclick.

### New APIs and helpers

- `GET/PATCH /api/v2/servers/<id>/properties` (`api/servers/server/
  properties.py`): reads/writes common server.properties keys, rewrites only
  changed lines, `\uXXXX` for non-ASCII on Java.
- Server PATCH accepts `mem_min` / `mem_max` (MiB); only `-Xms`/`-Xmx`
  in the start command change.
- `GET /api/v2/servers/<id>/players` (`players.py`): online/cached players,
  banned, whitelist + whitelist on/off, ops (from the game's JSON files).
- `GET /api/v2/servers/<id>/tasks` lists schedules (was a 500).
- `misc.js`: `escapeHtml()`, `bindEnabledSwitches()` (schedule/webhook
  on/off switches; flips only after the PATCH succeeds, keeps wide table,
  phone table and details popup in step, re-syncs on DataTables redraw).
- Translations: only `en_EN.json` is updated. Edit it with Python's `json`,
  sort just the section you touched, write with `indent=4,
  ensure_ascii=False` plus a trailing newline.

### Session 3: what the owner approved, and how it was built

- **Config tab** (`server_config.html`, `crafty-config.css`): sections
  (General, Game settings, Startup, Status checks, Crashes and shutdown),
  sticky save bar, unsaved-changes warning, danger zone. `#game-settings`
  anchor is linked from the Players tab.
- **Players tab** (`server_admin_controls.html`, `parts/server_players.html`,
  `crafty-players.css`): commands go through `/stdin`; lists reload from
  `/players` 1.5 s later. Hytale uses `op add/remove` and `unban`.
- **Backups tab** (`server_backup.html`, `crafty-backup-list.css`,
  `backup_mgr.py` summaries).
- **File manager** (`files.js`, `server_files.html`, `crafty-files.css`):
  `fileTypeName()` map; path bar crumbs use paths **relative** to the
  server folder (a leading `/` is treated as absolute by the files API and
  fails the traversal check); columns other than name/options are
  `d-none d-sm-table-cell`, phones get a meta line instead; the options
  button opens the context menu under itself when used from the keyboard
  (`context-menu.js`).
- **Metrics** (`server_metrics.html`): three Chart.js charts (CPU, memory,
  players; players only for Java/Hytale) with zoom/pan kept in sync
  (`syncTimeAxis`), preset ranges from `data['time_range_presets']`,
  default last hour (`panel_handler.py`).
- **Phone header** (`details_stats.html`, `crafty-server-overview.css`):
  below 576px the title row and extra stats hide behind "More details".
- **Logs** (`server_logs.html`): "Hide lines containing" filter with chips,
  hidden count, empty state, link to the Terminal, and "Older logs" link
  from the Terminal. **Not merged into the Terminal tab** as first
  suggested: Logs and Terminal have separate permissions (LOGS vs
  TERMINAL), so merging would change who can see what. Told the owner.
- Session 4 (`1b91543a`): schedule/webhook switches, restore spinner on
  error, snapshot restore confirmation (snapshot restore **deletes the
  server folder** first, see `backup_mgr.snapshot_restore`), editor saves
  one at a time (`editor.js` `save()` queues one follow-up save).

### Template gotchas (cost time before)

- Never wrap a `{{ ... }}` or `{% ... %}` expression across lines: Tornado
  raises a SyntaxError on the whole page. Compute with `{% set x = ... %}`.
- Check a template compiles before restarting:
  `python -c "from tornado.template import Loader;
  Loader('app/frontend/templates').load('panel/X.html')"` (in the venv).
- Pass strings to JS with
  `{% raw json_encode({key: translate(section, key, data['lang']) for key in [...]}) %}`.
- jQuery `.data()` caches values; change state with `.attr()` +
  `getAttribute`, or `.data(key, value)`, never mix.

### Still open

- A 424 response shows in the console on the metrics and header pages; it
  comes from a request unrelated to these changes (not investigated).
- The editor page never reaches Playwright's `networkidle`; tests use `load`.

### Deliberately not changed (checked, not bugs)

- Hytale "download_exe" doesn't redirect after create: on purpose, the
  `hytale_auth` websocket event does the redirect.
- Enrolling TOTP clears the `token` cookie: on purpose, forces a re-login
  so the session carries the MFA claim.
- Ko-fi / Patreon errors on the Contribute page come from their embeds.
- "No internet" popup when starting a server: sandbox only.

### Put off for later

- Settings: preset/tier rows silently dropped; activity-log and custom-login
  fetch failures not shown; add-user page uses `id=-1`; passkeys over HTTP
  give a confusing message.
- Dashboard accessibility and hard-coded English strings.
- Wizard nits: `roles_select` scoping, duplicate ids, bedrock "Server Upload"
  string.

## Session 5: README and screenshots

- The owner asked for a README that explains the fork to other people, with
  pictures. `README.md` now has: summary table, before/after screenshots per
  area, bug and security fix lists, install from source (the upstream Docker
  images do not include these changes), credits and license.
- Screenshots live in `docs/screenshots/<name>-before|after.png|jpg`
  (`docs/` is in `.dockerignore`). To retake them:
  1. Make an upstream copy of your test Crafty, data included: copy the
     whole folder (with `app/config/`, `servers/`, `backups/`), then
     `git archive fe65b372 | tar -x -C <copy>` to put the plain Crafty
     4.11.0 code (commit `fe65b372`) over it. `tar` is built into Windows
     10 and newer.
  2. Start server 1 in each first so the header shows live numbers. With
     the copy running (`python main.py -d -i` in the copy), run
     `node readme_shots.js before <dir>` from `dev/handoff-tools/`; stop
     it, start the fork and run `node readme_shots.js after <dir>`. Both
     use port 8443, so only one can run at a time.
  3. Look at every image before committing it: no machine details (paths,
     user names, environment values) in the Terminal or anywhere else.
     The cloud containers printed `JAVA_TOOL_OPTIONS` into the console,
     which is why `start.sh` unsets it.
  4. Use clean test data (normal player names and files); the XSS test
     files and players look odd in a README.
  5. Shrink: `convert X.png -strip -define png:compression-level=9`, and
     JPEG (`-quality 84`) for the login shots (photo background).

## Session 6: Docker image, install and migration docs (UNFINISHED)

The request is item 8 in "What the owner asked for". It was handed off
part-way through.

### Status

Done (committed with this file):

- `Dockerfile`: added `ARG TARGETARCH`. Upstream's apt step checks
  `$TARGETARCH` to install `lib32gcc-s1` (needed by SteamCMD) on amd64, but
  never declared the arg, so it was always empty and the library was never
  installed. Meanwhile `docker_launcher.sh` tells amd64 users that SteamCMD
  support is there. Also relabelled the image for the fork (title, url,
  source, documentation, maintainer); the old labels pointed at upstream.
- Built the image on amd64 (Docker 29, BuildKit): **the build succeeds**, and
  the log shows `lib32gcc-s1` and `libc6-i386` being installed. In the
  cloud sandbox pip needed the sandbox proxy's certificate, so that test
  build used a throwaway copy of the Dockerfile with two extra lines. The
  committed Dockerfile has no such lines and needs none elsewhere.
- Draft publish workflow (session 12: now live as the `docker` job of
  `.github/workflows/ci.yml`, see "Session 12").

Not done:

1. **The image has never been run.** Not yet checked: the panel starts,
   `/login` returns 200, `config/default-creds.txt` appears, login works, a
   server can be created and started, and `dpkg -s lib32gcc-s1` inside the
   container. The arm64 image has not been built at all, although the
   README already says the image works on arm64. Upstream builds arm64 the
   same way, so it probably does, but it is unchecked.
2. **Nothing is published.** The cloud session had no Docker Hub account or
   credentials, so it could not create a Docker Hub repo or push to one.
   The owner asked to be told if that was the case; **tell them plainly.**
3. The README "Install" section has not been rewritten. There are no update
   or migration instructions yet; the README has only a three-line "Moving
   over" note.
4. The owner thinks the README "has not been changed". It has: GitHub's
   default branch shows commit `8806e7ec` with the new README (checked
   through the GitHub API in session 6). Most likely a cached page, or they
   judged by the top, which still opens with the same Crafty logo as
   upstream. Tell them, give the link
   https://github.com/GiorgosPap777/Better-Crafty, and make the top of the
   README clearly different. Put the title and a one-line summary first,
   with a screenshot instead of the Crafty logo. Opening with Crafty's logo
   also makes the fork look official.

### Next steps, in order

1. The owner was told about points 2 and 4 at the end of session 6
   (nothing published, no Docker Hub access from the cloud; the README did
   change). Still to ask: their Docker Hub username, and Docker Hub only or
   also `ghcr.io`. The README top change in point 4 is still to do.
2. Run the image (adapt the paths on Windows):
   ```sh
   docker build -t better-crafty:test .
   mkdir -p ~/bc-test && cd ~/bc-test
   docker run -d --name bc-test -p 9443:8443 \
     -v "$PWD/config:/crafty/app/config" -v "$PWD/servers:/crafty/servers" \
     -v "$PWD/backups:/crafty/backups" -v "$PWD/logs:/crafty/logs" \
     -v "$PWD/import:/crafty/import" better-crafty:test
   docker logs -f bc-test      # wait until the web server is up
   curl -k -o /dev/null -w '%{http_code}\n' https://localhost:9443/login   # expect 200
   sudo cat config/default-creds.txt
   docker exec bc-test dpkg -s lib32gcc-s1 | head -2
   ```
   Then log in, create or import a server, start it, and look at a few tabs.
   Clean up with `docker rm -f bc-test`.
3. Publish (see "Publishing" below).
4. Rewrite the README (see "README plan" below), using the published image
   name.
5. Test the new instructions before pushing them (see "Testing the
   instructions" below).
6. Commit, push, and update this file.

### Publishing

Two ways. Let the owner choose; both can be used.

**a. From the PC.** The owner runs `docker login` themselves (never handle
their token in chat). Then:
```sh
docker buildx create --use --name bc        # once
# Only on a plain Linux amd64 host (Docker Desktop already has this):
docker run --privileged --rm tonistiigi/binfmt --install arm64
docker buildx build --platform linux/amd64,linux/arm64 \
  -t <dockerhub-user>/better-crafty:latest \
  -t <dockerhub-user>/better-crafty:sha-$(git rev-parse --short HEAD) \
  --push .
```
The first push to `<user>/better-crafty` creates the Docker Hub repo. Its
visibility follows the account's default privacy setting, so check on
hub.docker.com that it is public, and add a short description that links to
the GitHub repo. The arm64 half builds under emulation and can be slow.

**b. GitHub Actions** (session 12: this is now the `docker` job in
`.github/workflows/ci.yml`; tags changed, see "Session 12"):

- Publishes only from the default branch and from `v*` tags; it can also be
  run by hand. Pushes that change only `**.md`, `docs/**` or `dev/**` do not
  trigger a build.
- Always pushes to `ghcr.io/<owner, lower case>/better-crafty` using the
  built-in `GITHUB_TOKEN` (`packages: write` is set in the file). It also
  pushes to Docker Hub as `<DOCKERHUB_USERNAME>/better-crafty`, but only
  when the repository secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`
  exist. The token is a Docker Hub personal access token with Read & Write
  access (Docker Hub → Account settings → Personal access tokens). The
  owner adds both under GitHub repo → Settings → Secrets and variables →
  Actions.
- Tags: `latest` from the default branch, `X.Y.Z` and `X.Y` from a `vX.Y.Z`
  git tag, and `sha-<short>` always. The version label comes from
  `app/config/version.json`. Builds amd64 and arm64 (QEMU), with the GitHub
  Actions cache.
- Checked so far: the YAML parses, and the image-name shell step was
  dry-run in bash both with and without the Docker Hub secrets. (An earlier
  version leaked a `::notice::` line into the image list; that is fixed.)
  **It has never run on GitHub.**
- New `ghcr.io` packages may start out private. To fix: GitHub profile →
  Packages → better-crafty → Package settings → Change visibility → Public.
- Pushing a file under `.github/workflows/` needs a git credential with
  the `workflow` scope. If GitHub refuses the push, that is why.
- If the owner wants Docker Hub only, remove the `ghcr.io` login step and
  image line.

### README plan

- **Top:** `# Better Crafty`, a one-line summary, then a screenshot
  (`docs/screenshots/terminal-after.png`). Move the Crafty logo out of the
  top, or drop it.
- **Contents line:** add Update and Moving from Crafty.
- **Install**
  - *What you need:* Linux on amd64 or arm64 (for example a Raspberry Pi 4
    or 5 on a 64-bit OS) with Docker, or Python 3.9+ and Java for the way
    without Docker. There is no Windows build. Keep the existing warning
    about Docker on WSL / Docker Desktop corrupting worlds.
  - *Docker Compose (recommended):* a `docker-compose.yml` with
    `image: <published name>:latest`, plus the same ports and volumes as
    `docker/docker-compose.yml`. Keep the container paths `/crafty/...`
    exactly as they are. Run `docker compose up -d`, then get the admin
    password from `config/default-creds.txt`, which is written on the first
    start. It has mode 600 and is owned by the container's `crafty` user, so
    the host may need `sudo cat` (not verified). Open
    `https://<server-ip>:8443`, accept the warning about the self-signed
    certificate, log in as `admin`, and change the password. Mention `TZ`.
  - *docker run:* the same, using `-v "$(pwd)/config:/crafty/app/config"`
    and so on.
  - *Build it yourself:* the current text
    (`cd Better-Crafty/docker && docker compose up -d --build`).
  - *Without Docker (Linux):* use the same layout as Crafty's official
    installer, so that the migration steps line up. **Untested:**
    ```sh
    sudo apt update
    sudo apt install -y git python3 python3-venv python3-dev gcc
    sudo apt install -y openjdk-21-jre-headless   # the Java your Minecraft version needs
    sudo mkdir -p /var/opt/minecraft
    sudo useradd --system --create-home --home-dir /var/opt/minecraft/crafty --shell /bin/bash crafty
    cd /var/opt/minecraft/crafty
    sudo -u crafty git clone https://github.com/GiorgosPap777/Better-Crafty.git crafty-4
    sudo -u crafty python3 -m venv .venv
    sudo -u crafty .venv/bin/pip install -r crafty-4/requirements.txt
    ```
    Then add `/etc/systemd/system/crafty.service`:
    ```ini
    [Unit]
    Description=Better Crafty
    After=network.target

    [Service]
    Type=simple
    User=crafty
    WorkingDirectory=/var/opt/minecraft/crafty/crafty-4
    ExecStart=/var/opt/minecraft/crafty/.venv/bin/python main.py -d
    Restart=on-failure

    [Install]
    WantedBy=multi-user.target
    ```
    Run `sudo systemctl daemon-reload && sudo systemctl enable --now crafty`.
    The password is in
    `/var/opt/minecraft/crafty/crafty-4/app/config/default-creds.txt`, and
    the logs are in `journalctl -u crafty -f`. Mention opening 8443/tcp and
    the game ports in the firewall.
- **Updating**
  - Compose with the image: `docker compose pull && docker compose up -d`.
  - Built yourself: `git pull && docker compose up -d --build`.
  - Without Docker:
    1. `sudo systemctl stop crafty`
    2. `cd /var/opt/minecraft/crafty/crafty-4`
    3. `sudo -u crafty git pull`
    4. `sudo -u crafty ../.venv/bin/pip install -r requirements.txt`
    5. `sudo systemctl start crafty`
- **Moving from the original Crafty Controller**
  - Everything carries over (users, roles, servers, schedules, backups,
    settings): the fork uses the same database and folders and makes no
    database changes, so switching back works too.
  - *Versions:* the fork is 4.11.0, which was still upstream's latest
    release when checked on 2026-10-15 (upstream master `fe65b372`, last
    upstream commit 2026-09-16). Re-check before publishing.
    - From 4.11.0: drop-in.
    - From an older 4.x: works. Crafty's normal migrations upgrade the
      database on the first start, and after that going back needs 4.11.0
      or a backup.
    - From anything newer than 4.11.0: not supported until the fork
      catches up.
  - *Back up first:* at least the config folder, which holds the database,
    users and settings.
  - *Docker:*
    1. `docker compose down`.
    2. Back up.
    3. Change only the `image:` line
       (`registry.gitlab.com/crafty-controller/crafty-4:latest` or
       `arcadiatechnology/crafty-4:latest`) to the new image, and keep the
       volumes as they are.
    4. `docker compose pull && docker compose up -d`.

    With docker run: `docker stop` and `docker rm` the container (the data
    lives in the mounted folders), then run the same command with the new
    image name.
  - *Official Linux installer:* switch the code **in place**. Crafty stores
    each server's absolute path in its database, so never install into a
    new folder and copy the data across.
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
    - `--track origin/HEAD` resolves to the fork's default branch, whatever
      it is called. This was tested on a toy repo: tracking was set to the
      real branch name, and `git pull` worked afterwards.
    - After switching, **do not use the installer's `update_crafty.sh`**.
      It runs `git reset --hard origin/master` (the fork has no `master`)
      and then `git pull`. Use the Updating steps instead.
    - The installer's `run_crafty.sh` and `crafty.service` keep working,
      because the paths are the same.
    - If `git checkout` complains about local changes, the files were
      edited by hand; run `git stash` first.
  - *Going back:*
    - Docker: restore the old `image:` line, then pull and `up -d`.
    - Linux: stop the service, then
      `sudo -u crafty git checkout master` (or `dev`, whichever they ran
      before), pip install, and start again.
  - Windows installs are not covered, because the fork has no Windows
    build.

### Testing the instructions

- **Clean install:** in a fresh `ubuntu:24.04` container, run the "Without
  Docker" steps. Skip systemd and start with
  `cd /var/opt/minecraft/crafty/crafty-4 && sudo -u crafty ../.venv/bin/python main.py -d`.
  Check that `/login` returns 200 and the creds file appears.
- **Linux migration:**
  1. In another container, set up upstream the way the installer does:
     `git clone https://gitlab.com/crafty-controller/crafty-4.git` into
     `/var/opt/minecraft/crafty/crafty-4`, check out `master`, then create
     the venv and run pip install.
  2. Start it once, log in, add a user and import a server, then stop it.
  3. Run the migration commands, start the fork, and check that the same
     admin login works and the data is all there.
  4. Run the "going back" steps and check that upstream starts again.
- **Docker migration:** run the upstream image with a data folder, stop it,
  switch the image, start it, and check the login and the data.

### Facts already checked (no need to redo)

- **Official installer** (gitlab.com/crafty-controller/crafty-installer-4.0,
  read in session 6):
  - Default `install_dir` is `/var/opt/minecraft/crafty`. It clones
    `https://gitlab.com/crafty-controller/crafty-4.git` into `crafty-4`
    there and creates the venv `.venv` next to it.
  - User `crafty`, created with `useradd crafty -s /bin/bash`.
  - Writes `run_crafty.sh`, `run_crafty_service.sh`
    (`python3 main.py -d`) and `update_crafty.sh`. `crafty.service` runs
    `run_crafty_service.sh` as `crafty`.
  - The user picks the `master` or `dev` branch.
- **`.gitignore`** covers `app/config/`, `/servers/`, `/backups/`,
  `/import/`, logs, `*.sqlite`, and the custom login, embed and logo image
  folders under `app/frontend/static/assets/images/`. The only tracked
  files in `app/config` are `credits.json`, `default.json.example`,
  `logging.json`, `motd_format.json` and `version.json`. So switching
  branches never touches user data.
- **Docker files:** `docker/docker-compose.yml` is unchanged from upstream
  and builds from source (`build: ..`). On the first start,
  `docker_launcher.sh` copies the default config and fixes permissions;
  then it runs Crafty as `crafty`. It refreshes `version.json` in the
  config volume on every start.
- **`main.py`:** `-d` / `--daemon` means no interactive prompt. The first
  start writes `app/config/default-creds.txt` (JSON with username `admin`
  and the password) with mode 600.
- **Not checked:** what port 8000 actually does. The README currently
  calls it "HTTP".

## Session 7: player management (done)

The owner asked for player management "( inventorys , statistics etc)". All
of it is read-only and comes from the world's save files, so it works while
the server is stopped and changes nothing.

### What was built

- **Players list** (Player management tab): everyone who has ever joined,
  not only who is online. Rows come from `playerdata/*.dat` merged with
  Crafty's own `players_cache.json` (names matched case-insensitively).
  Shows play time and last played; a search box appears from 8 players;
  the first 50 are shown, then "Show more" adds 200. A player whose name is
  not in `usercache.json` shows as "Unknown name" with the UUID.
- **Details window** (Bootstrap `modal-xl`, scrollable) with tabs:
  - Overview: health, food, level and XP bar, game mode, location and
    dimension, spawn point, last death. Kick, ban, op/deop, whitelist and
    a game mode select (`gamemode <mode> <name>`); these send console
    commands, so they only show while the server runs.
  - Inventory: armor and off hand row, main inventory 9-35, hotbar 0-8
    with the selected slot outlined. Clicking an item shows its id, count,
    custom name, enchantments (roman numerals), durability (computed from
    a table of max durabilities in the JS), potion, and what is inside
    shulker boxes and bundles.
  - Ender chest, Statistics (11 summary cards, top-10 lists for mined,
    killed, killed by, crafted, used; a searchable table of every stat,
    300 rows at most), Advancements (done ones, recipes left out).
  - "Last saved" uses the `.dat` file time. While the server runs, **Save
    now** sends `save-all` and reloads after 3 seconds.
- The list refreshes when the set of online players changes.

### Files

- `app/classes/helpers/player_data.py` (new): a small NBT reader (gzip or
  plain; size, depth and list-length limits, raises `NbtError`), item
  parsing, `world_folder()` (reads `level-name`, refuses folders outside
  the server), `list_players()`, `player_details()`.
- `app/classes/helpers/server_properties.py`: `read_value(path, key)`.
- `servers_controller.py`: `get_player_overview()` now has `known` (list
  from the save files, `null` for non-Java servers);
  `get_player_details(server_id, uuid)`.
- `api/servers/server/players.py`: shared `_authorize_players()` (server
  access plus the Players permission) and the new handler.
  **API:** `GET /api/v2/servers/<id>/players/<uuid>` returns
  `{"status":"ok","data":{...}}`; 400 `INVALID_PLAYER` for a bad UUID or a
  non-Java server; 404 `PLAYER_NOT_FOUND` when there is no save data.
- `panel/parts/server_players.html`, `panel/server_admin_controls.html`
  (all the JS), `css/partial/crafty-players.css`, 87 new keys under
  `serverPlayerManagement` in `en_EN.json`. Other languages fall back to
  English; `translate(..., False)` keeps missing keys out of the error log.
- `tests/classes/helpers/test_player_data.py`: 23 tests, with an NBT writer
  in the test file (also used by `dev/handoff-tools/player_fixtures.py`).

### Save format differences handled

- Item data in `components` (1.20.5+) or `tag` (older). Enchantments wrapped
  in `levels` in 1.20.5-1.21.4, flat from 1.21.5, a list before 1.20.5.
- Armor and off hand in the `equipment` compound (1.21.5+) or Inventory
  slots 100-103 and -106 (older). Respawn point in `respawn` (1.21.5+) or
  `SpawnX/Y/Z`.
- Stats: nested by category (1.13+) or flat `stat.*` keys (1.12).
  `play_one_minute` became `play_time` in 1.17; both count ticks.

### Not done (ideas if the owner wants more)

- Bedrock servers: their player data lives in the LevelDB world database,
  which needs a LevelDB reader. The details button only shows for Java.
- Editing inventories (would need the server stopped and NBT writing).
- Item icons: names only, because Minecraft's textures cannot be shipped.

## Session 8: command suggestions in the Terminal (done)

The owner asked for "auto complison in the command like like in the game".
Typing in the Terminal's command box now opens a list like the Minecraft
Java chat box: commands, then arguments (players, selectors, items, blocks,
effects, enchantments, game rules, coordinates...), with a usage hint such
as `<item> [<count>]` when nothing can be listed (free text, numbers).

### How it behaves

- **Tab** takes the highlighted suggestion (adds a space when more can
  follow); **Shift+Tab**, **↑**, **↓** move; **Enter** takes it only after
  moving with the arrows, otherwise Enter sends what was typed; **Esc**
  hides the list until Tab or more typing. With the list closed, ↑ and ↓
  are the old command history.
- Player names: online (from the live stats ping sample) first, then
  everyone in the Players API (`known`, `players`), A to Z. Needs the
  Players permission; without it only selectors are offered. As in the
  game, `pardon` lists banned players, `deop` operators, `whitelist remove`
  the whitelist; `op`, `ban`, `whitelist add` skip people already on that
  list; `pardon/op/deop/whitelist add|remove` get no `@` selectors.
- Version: the newest data file not newer than the server. Sources, best
  first: the server's own log line `]: Starting minecraft server version X`
  (the `]: ` keeps a chat message from spoofing it), the live stats version
  while running, the jar name. Unknown means the newest data. Below 1.13 and
  proxies (Velocity, BungeeCord, Waterfall, Travertine) get no suggestions;
  only `minecraft-java` servers get the feature at all.
- Plugin and mod commands are not known (there is no way to ask a running
  server for its command tree from the console), so they get no
  suggestions but are still sent.

### Data files

`app/frontend/static/assets/data/commands/java-<version>.json`, made by
`dev/command-data/generate.py` from the game's own data generator
(`--reports`): the Brigadier command tree plus ID lists. Shipped:
1.16.5, 1.18.2, 1.19.4, 1.20.1, 1.20.4, 1.21.1, 1.21.4, 1.21.8, 1.21.10,
1.21.11, 26.1, 26.3 (about 50-105 KB each). To add a version:

```
python dev/command-data/generate.py --java /path/to/java 26.4
```

It downloads the jar from Mojang (checks the sha1, resumes broken
downloads). Java needed: 17 for 1.18-1.20.4, 21 for 1.20.5-1.21.11, 25 for
26.x. Nothing else needs changing: `command_data.java_versions()` lists the
folder (cached until restart).

Format: `{"version", "root", "nodes", "ids"}`. A node is
`[name, flags (1 argument, 2 executable), child ids, parser, properties,
redirect path]` with trailing nulls dropped; identical branches are shared
(26.3: 2475 nodes become 921). Game rules appear as `x` and `minecraft:x` in
the report; one is kept. `execute run` has no children or redirect in the
report, so it is stored as a redirect to the root (`[]`). Data-driven lists
(enchantments, biomes, structures, damage types) come from the nested
jar's `data/minecraft/<name>/` folder (plural folder names before 1.21).
Lists over 400 entries are left out except items and blocks; recipe
advancements, template pools and test instances are skipped.

Version facts worth knowing: 1.21.11 renamed game rules to snake_case
(`keep_inventory`); versions are year based from 26.1; `@n` exists from
1.21.

### Files

- `app/frontend/static/assets/js/shared/command-complete.js` (new): the
  parser and the popup. `CommandComplete.complete(tree, input, players,
  text)` is pure and runs in node too; `attach(input, options)` builds the
  popup (ARIA combobox/listbox) and returns `{handleKey, close, refresh,
  setVersion}`.
- `app/classes/helpers/command_data.py` (new), `panel_handler.py` (passes
  `command_versions` on the `term` subpage for Java servers).
- `panel/server_term.html`: data attributes on `#command-form`, the player
  lists, version sources, key handling order (suggestions first, then
  history). `crafty-terminal.css`: `.cmd-suggest` styles. 11 keys under
  `serverTerm` in `en_EN.json`.
- Tests: `tests/classes/helpers/test_command_data.py` (pytest);
  `node dev/command-data/test_complete.js` (checks against the real data
  files, no browser); `dev/handoff-tools/test_complete.js` and
  `test_complete_phone.js` (browser, server S1).

### Not done (ideas)

- Plugin/mod commands: Paper could expose its tree through a plugin, which
  is out of scope for a panel.
- Bedrock: its command list is not published the same way.
- Checking a whole command for errors before sending (the game underlines
  mistakes in red).

## Session 9: handoff to the owner's PC (done)

- `CLAUDE.md` (repo root): loaded automatically by Claude Code; points here
  and lists the working rules and the checks to run before each commit.
- The browser scripts in `dev/handoff-tools/` now run in place on any OS.
  `local.js` holds what they share: the Crafty URL and folder, the test ids,
  the API token, Playwright and Chromium, and a TOTP code generator (so
  `totp.py` and `mk_mfa_user.py` are gone). `package.json` pins Playwright.
- `setup_testdata.py` builds all the test data on a fresh Crafty through the
  API in about 15 seconds; `fake_server/` holds the fake Minecraft server it
  uses (source and a Java 8 jar).
- Checked on a brand-new Crafty with only these steps: every suite passes.
  Tests that had relied on old data now make their own (`test_audit.js`
  adds its own schedule; `test_files.js` undoes its rename and upload).
- Bug fixed on the way: `/panel/edit_role?id=<unknown>` crashed with a 500
  (upstream); it now goes to the "Invalid Role ID" error page
  (`panel_handler.py`).
- Server, backup and other ids are UUIDs and can start with a digit, which
  a CSS `#id` selector does not allow. jQuery's `$("#" + id)` still works
  (it uses `getElementById`), but `querySelector` and Playwright do not: use
  `[id="..."]` in tests.
- API facts learned (they cost time):
  - A token issued in the same second as a change to that user (such as
    creating it) is refused (`valid_tokens_from`). Wait 2 seconds before
    logging in as a user you just made.
  - TOTP set-up: `POST /api/v2/users/<id>/totp/` (there is no `@me` route
    for it) returns `otp.id` and `otp.totp_secret`; confirm it with
    `POST /api/v2/users/@me/totp/<otp id>/verify/` and
    `{"name": ..., "totp": <6 digits>}`, which returns the backup codes.
  - `GET /api/v2/servers/<id>/backups/` returns an object keyed by backup
    id, not a list. Backup files go to `<backup_location>/<backup_id>/`.
  - Importing a server: put the zip in `<crafty>/import/upload/`, then
    `POST /api/v2/servers/` (see `import_servers()` in
    `setup_testdata.py`); the answer has `data.new_server_id`.
  - Python `requests` ignores `verify=False` when the environment sets a CA
    bundle; `session.trust_env = False` fixes it.

## Session 10: item pictures and the game's inventory (done)

The owner asked for item pictures and an inventory that looks like the
game's in the player details window.

### Where the pictures come from

Mojang's textures may not be put in this repo or the Docker image, so the
pictures are opt-in and made on the owner's machine:

- In the player details window (Inventory or Ender Chest tab) a super user
  sees an offer and a **Show item pictures** button. Other users see a
  short hint instead.
- Crafty reads Mojang's version list, downloads the latest release's client
  jar (about 40 MB) from Mojang, and checks its SHA-1. It then draws a
  64x64 PNG for each item, keeps only the pictures in
  `app/config/item_icons/` (with `info.json`: version, count, made), and
  deletes the jar. On a fast line this takes about 3 seconds to download
  and 4 seconds to draw. The page shows progress, and an error offers
  **Try again**.
- **Get them again from the newest version** (super users) redoes it after
  a Minecraft update. The new set replaces the old one in one step
  (`item_icons.new`, then a rename).
- Starting it adds an entry to the audit log.
- `.dockerignore` leaves `app/config/item_icons*` out, so an image built
  from a checkout that has pictures never ships them.
- It always uses the latest release, because only 1.21.4 and later jars
  have the `items/` definitions it reads. Ids from older worlds mostly still
  match.
- Checked end to end against Mojang's real servers in session 10: 26.3
  drew 1630 of 1658 items.

### How items are drawn (`app/classes/helpers/item_icons.py`, Pillow only)

- **Item definitions** (`assets/minecraft/items/<name>.json`):
  - model: drawn
  - select: the case for the `gui` display context, else the fallback
  - condition: `on_false`
  - composite: all of its models
  - range_dispatch: the fallback
  - special: see below
- **Flat items** (`builtin/generated`): layers `layer0..N`, each with its
  tint (constant, dye, grass colormap, or the default of the others).
- **Block models**: drawn in 3D with the model's `display.gui` rotation,
  translation and scale. Faces are lit like the game's inventory (top 100%,
  left 81%, right 62%) when `gui_light` is `side`. Drawing is at 4x size,
  then scaled down. Mirroring transformations flip the faces back.
- **Specials** are drawn from the entity textures:
  - chests
  - shulker boxes
  - skeleton, wither skeleton, zombie and creeper heads
  - player heads (always Steve)
  - shield
  - conduit
- **Not drawn**: banners, decorated pots, dragon and piglin heads, copper
  golem statues and a few others. The slot shows the item's name instead,
  so nothing breaks.
- **Sprites** are saved too: the empty armour and shield slot outlines,
  the enchantment glint, hearts, food and the XP bar. Their names start
  with `_`.

### API

- `GET /api/v2/crafty/item_icons/` (any signed-in user) returns
  `{state: none|working|ready|error, version, count, made}`. While working
  it also has `step` (download/draw), `done` and `total`; on an error it has
  `error`.
- `POST` to the same address (super users only) starts the work. A second
  press while it is running does nothing.
- `GET /api/v2/crafty/item_icons/<name>.png` serves one picture to signed-in
  users. Names must match `[a-z0-9_]{1,64}`. Pictures are cached for a week,
  and the page adds `?v=<made>` so a new set replaces the old one.

### The page (`server_admin_controls.html`, `crafty-players.css`)

- **Inventory tab, with pictures**, laid out like the game's inventory
  screen:
  - armour column with the empty-slot outlines
  - a black box with the player's name, game mode and dimension
  - the off-hand slot
  - hearts, food and the XP bar with the level, from the save
  - main grid
  - hotbar, with the selected slot framed in white
- **In each slot**:
  - stack count
  - durability bar
  - moving enchantment glint (still when the system asks for reduced
    motion)
  - white highlight on hover
- **Tooltip** on mouse hover, styled like the game's:
  - the name (aqua if enchanted, italic if renamed)
  - enchantments
  - potion
  - up to 5 contents, then "and N more"
  - durability
  - id
- **Details box**: a click fills it. It sits beside the inventory on wide
  screens and below it on phones (scrolled into view). Shulker box and
  bundle contents appear there as a small grid placed by slot
  (`parse_item` now keeps each content's `slot`).
- **Ender Chest tab**: a chest panel.
- **Statistics tab**: the top lists for mined, crafted and used get small
  pictures.
- **Without pictures**: the named cards from session 7 stay, with the
  offer or the hint above them.
- **Sizes** are in game pixels (`--p`): 3 screen pixels when there is room,
  else 2, else whatever fits on narrow phones. This uses CSS container query
  units and `round()`, so the pictures stay sharp.

### Files

- `app/classes/helpers/item_icons.py` (new): renderer, downloader,
  `ItemIcons` status and job
- `app/classes/web/routes/api/crafty/item_icons.py` (new), routes in
  `api_handlers.py`
- `app/classes/helpers/player_data.py`: `slot` on container contents
- `app/frontend/templates/panel/server_admin_controls.html`,
  `app/frontend/static/assets/css/partial/crafty-players.css`
- `app/translations/en_EN.json`: `itemPictures*` and `moreItems` under
  `serverPlayerManagement`
- `tests/classes/helpers/test_item_icons.py` (new, 12 tests): a tiny fake
  jar made with Pillow; covers drawing, lighting, select, condition,
  composite, missing parts, name checks, the folder swap, the checksum
  check (fake `requests` session) and error reporting
- `.dockerignore`: leaves the pictures out of images
- `dev/handoff-tools/test_item_icons.js` (new);
  `test_player_details.js` now fakes "no pictures" so it still checks the
  cards
- `README.md`: an "Item pictures" paragraph in the Players section;
  `docs/screenshots/player-inventory-after.png` and
  `player-stats-after.png` retaken with pictures (`readme_shots.js` now
  clicks the first slot by its label, then moves the mouse away so no
  tooltip is in the shot)

### Testing the page

`test_item_icons.js` needs pictures in the test Crafty. Either press the
button once (needs internet), or draw them from a client jar you already
have, from the repo folder:

```
python -c "import json, zipfile, datetime; from pathlib import Path; from app.classes.helpers.item_icons import Assets, render_all; out = Path('<crafty>/app/config/item_icons'); out.mkdir(parents=True, exist_ok=True); n = render_all(Assets(zipfile.ZipFile('<client.jar>')), out); (out / 'info.json').write_text(json.dumps({'version': '<version>', 'count': n, 'made': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}))"
```

The script also fakes the status API with `page.route` to check the offer,
the progress, the switch to pictures and the error, without downloading.

### Not done (ideas)

- Draw banners (pattern layers), decorated pots and the remaining special
  items.
- Potions all show the default potion colour; their real colours would need
  a table of effect colours.
- Player heads always show Steve. Real skins would need Mojang's session
  servers.
- Show the player's own skin in the black box.

## Session 11: skin, HUD layout, bug review (done)

The owner asked for the HUD below the inventory like the game, the
player's skin, and a check for serious bugs because they will run their
real server on this fork.

### Left for later

- About 90 error pop-ups put the API's error text into the page without
  `escapeHtml()`. Done in session 12 ("Error pop-ups").
- Drawing the special items the owner asked about (waiting for their
  choice; see the answer below).

### Done and pushed (`423d2a9c`)

- **HUD like the game**: XP level and bar right below the inventory panel,
  hearts below it on the left, food on the right (`mcHud` in
  `server_admin_controls.html`). A spacer keeps food on the right when there
  is no health.
- **2x2 crafting grid**, the "Crafting" label, the arrow and the result slot,
  placed as in the game's inventory texture (content coordinates: grid at
  (90,10), arrow (128,22), result (146,20)). Always empty: the save does not
  keep it.
- **Player skin** drawn in the black box with a small z-buffer rasteriser in
  the page (`drawSkin`, canvas). It turns toward the mouse like the game's
  inventory (body and head yaw `atan(dx/40)*20 deg`, head pitch from dy),
  inner layer culled, outer layer (hat, jacket...) blended. Slim arms are 3
  pixels wide. Phones: follows a finger while it is down.
- **Where skins come from** (`app/classes/helpers/player_skins.py`, new):
  - only once item pictures exist (that is when Mojang's art is allowed);
  - version 4 UUIDs (online-mode accounts): Mojang's session server, then
    `textures.minecraft.net` only (checked by regex), at most 256 KB, PNG
    64x64 or 64x32. Kept in `app/config/player_skins/` for 6 hours; after a
    failure it waits 10 minutes before asking again and uses an old copy if
    there is one;
  - everyone else, or on failure: the game's default skin for that UUID
    (Java `UUID.hashCode()`, 9 skins x slim/wide), saved by the item picture
    maker as `_skin_<model>_<name>` sprites (`DEFAULT_SKINS` in
    `item_icons.py`). Picture sets made before this have no default skins:
    the box then shows the text as before;
  - old 64x32 skins get the game's clean-up (`normalise`).
- **API**: `GET /api/v2/servers/<id>/players/<uuid>/skin` (players
  permission; only players this server knows, so Crafty never looks up
  anyone else). PNG with header `X-Skin-Model: wide|slim`.
- `.dockerignore` leaves out `app/config/player_skins/`.
- Tests: `tests/classes/helpers/test_player_skins.py` (18),
  `test_has_player` in `test_player_data.py`; `test_item_icons.js` checks
  46 slots, the HUD position, the skin drawn and turning with the pointer.

### Bug review: found and fixed (`46684a64`)

- **`server.properties` could be emptied** by a crash or a full disk while
  saving game settings: it was rewritten in place. Now it is written to a
  temporary file in the same folder, synced, given the old file's
  permissions, then moved over it in one step (follows a symlink to the
  real file). `server_properties.write_changes`.
- **A text setting ending in `\`** (e.g. a MOTD) made Java join the next
  line onto it, silently losing that setting. An odd number of trailing
  backslashes now gets one more. `server_properties.validate_changes`.
- **Changing only the max memory rewrote the min flag too** (and the other
  way round), e.g. `-Xms512k` became `-Xms0M`. Now the flag that is not
  being changed stays exactly as written. `java_memory.set_memory`.
- **Config page, memory boxes** (`server_config.html`): the boxes only allowed steps of 0.125 GB, so a start
  command like `-Xmx3000M` (2.93 GB) made the browser refuse to save the
  whole config page. Now `step="any"`, `min="0"` (the server still checks
  128 MiB to 1 TiB). Also, GB rounding could change an untouched value by
  1 MiB on every save (`-Xmx448M` became `-Xmx449M`): `memoryChanges()` now
  skips a box whose value equals its `defaultValue`. `test_config.js` now
  checks both (`-Xms448M -Xmx3000M` saves and stays as written).
- Tests: `test_trailing_backslash_does_not_swallow_the_next_line`,
  `test_write_replaces_the_file_in_one_step` (symlink and mode kept, no
  leftover files), and a `-Xms512k` test in `test_java_memory.py`.

### Bug review: read and fine (no need to redo)

Back end: `server.py` (EULA check, stats job), `backup_mgr.py`, `tasks.py`,
`server_stats.py`, `servers_controller.py`, properties route, server create
and PATCH (memory), upload (names checked after decoding), login, public
handler (`safe_next_url`), passkeys, `panel_handler.py` (schedule, webhook,
backup and role ids checked against the server), schedule and webhook APIs
(ownership checks), item picture routes (name regex), `command_data.py`.
Front end: `files.js` (delete, rename, upload, editor links now
`encodeURIComponent`), `editor.js` (save queue, conflict prompt),
`server_backup.html` and `server_backup_edit.html` (start, delete plan,
restore), `server_config.html` (save, delete server), server header
start/stop/kill (`details_stats.html`), dashboard start/stop and stop all,
Terminal command sending, schedules and webhooks pages, the four new-server
wizards. Small back-end changes (`roles/index.py`, `passkey.py`,
`server_stats.py`: upstream already stored raw bytes, so old databases
read fine). **No database migrations were added**, so moving from upstream
4.11.0 keeps the database as is.

### Answer to the owner's question: why some items have no picture

In the game these items have no normal model in the game files. Their item
definition says `"type": "minecraft:special"`, and the game draws them with
Java code that holds their shape (the same code that draws the block or
mob). The picture maker reads only the game's data files, so for each such
item its shape has to be written by hand in `item_icons.py`
(`_special_model`, boxes like `CHEST`, `SHULKER`, `HEADS`). Done so far:
chests, shulker boxes, skeleton/wither skeleton/zombie/creeper heads,
player heads, shield, conduit. Not done:

- **Banners**: the cloth and pole are easy (one texture, dyed base
  colour). The patterns on each banner come from that item's data in the
  save, so a per-banner picture would be drawn in the page, not ahead of
  time. A plain banner of each colour is a small job.
- **Decorated pots**: a simple box shape; sides from the pot texture (the
  sherds on each side are per item, like banners). Small job for a plain
  pot.
- **Dragon head and piglin head**: different head shapes (dragon has a
  snout and jaw, piglin has ears and a snout). Medium job, boxes copied
  from the game's model code.
- **Copper golem statues**: the whole golem in a pose, four copper ageing
  stages. Biggest job.
- Others may be in the same group (session 10 drew 1630 of 1658 items).
  To list them, find the `special` types that `_special_model` returns
  None for.

Ask the owner which ones they want; plain banners, decorated pots and the
two heads are the best value.

### Files (session 11)

- `app/classes/helpers/player_skins.py` (new), `item_icons.py`
  (`DEFAULT_SKINS`, `_skin_*` sprites), `player_data.py` (`has_player`),
  `servers_controller.py` (`has_player`)
- `app/classes/web/routes/api/servers/server/players.py`
  (`ApiServersServerPlayerSkinHandler`), route in `api_handlers.py`
- `app/classes/helpers/server_properties.py`, `java_memory.py` (fixes)
- `app/frontend/templates/panel/server_admin_controls.html`,
  `static/assets/css/partial/crafty-players.css`,
  `templates/panel/server_config.html`
- `app/translations/en_EN.json`: `serverPlayerManagement.crafting`
- tests listed above; `dev/handoff-tools/test_item_icons.js`

## Session 12: suggestions (in progress)

The owner approved this list (from the session 12 chat) and asked to start;
they are doing the Docker Hub part themselves in parallel:

1. Update check pointed at this fork. **Done.**
2. Tests on GitHub, image published only when they pass. **Done.**
3. Version numbers and releases. **Done** (the machinery; the first
   release, `v1.0.0`, is not tagged yet, see below).
4. Keep up with the original Crafty. **Checked, nothing to merge yet.**
5. Escape the ~90 error pop-ups. **Done.** Also fixed an upstream bug
   found while testing it ("Database is locked" below).
6. Bigger features, in this order unless the owner says otherwise:
   restart with in-game warnings (**done**, see below), world tools
   (download the world as a zip, reset the Nether or the End), backups to
   another disk / network share / cloud, a Modrinth plugin and mod
   installer. Plus the special item pictures once the owner picks which.

### Waiting on the owner: Docker Hub

**Update:** the GitHub runs for `57ed1545` and `7bbdc549` passed every job
and their `docker` job logged in to Docker Hub and pushed `edge` and
`sha-...`, so the two secrets are already set. Still to do when the owner
says they are finished: steps 2 to 4 below (and ask for the username if
it is not in the run log).

They were told to: make a Docker Hub account, create a personal access
token with Read & Write access, add the GitHub repo secrets
`DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`, and tell us their username
(never the token). When they say it is done:

1. Check the latest "Tests and Docker image" run on GitHub (the `docker`
   job's "Choose image names" step says whether the Docker Hub secrets
   were found). The cloud session can read runs with the GitHub MCP tools
   (`actions_list`, `get_job_logs`).
2. Tag the first release (see "Making a release"), which publishes
   `latest`, `1.0.0` and `1.0`.
3. Ask them to check on hub.docker.com that the repo is Public; on GitHub,
   Packages → better-crafty → Package settings → Change visibility →
   Public for the `ghcr.io` copy.
4. Do the rest of "Session 6" (run the image, README install, update and
   migration sections) using `<username>/better-crafty:latest`.

### Update check (done)

- Upstream asked GitLab for Crafty's tags, so the fork would have shown
  "Update Available!" (linking to upstream's releases) for every upstream
  release; following it replaces the fork with upstream.
- `Helpers.check_remote_version()` now reads
  `https://api.github.com/repos/GiorgosPap777/Better-Crafty/releases/latest`
  (drafts and pre-releases are skipped; no release yet means 404, which is
  "no update") and compares its `tag_name` with the Better Crafty version.
  `Helpers.FORK_REPO` and `FORK_RELEASES` hold the repo name and the link.
  The announcement (bell menu) and the footer link go to the fork's
  releases page. Runs at start and every 12 hours, as before.
- Upstream's announcements feed (`craftycontrol.com/notify`) is still
  shown; it carries Crafty news and security notes.
- In the cloud sandbox the check logs "Unable to check" because the crafty
  user cannot read the sandbox's CA bundle; that is the sandbox only.

### Versions (done)

- `app/config/version.json` keeps upstream's `major`/`minor`/`sub` (the
  Crafty version the fork is based on: user agents, webhooks, support logs
  and the API still report it) and gains `"better_crafty": "1.0.0"`.
  `Helpers.get_fork_version()` reads it. The footer shows
  "Version: Better Crafty 1.0.0 (Crafty 4.11.0)".
- Docker installs get the new file on every start: `docker_launcher.sh`
  copies `version.json` from the image into the config volume.
- Semantic versions: bump the third number for fixes, the second for new
  features, the first for big or breaking changes. When merging a new
  upstream release, update `major`/`minor`/`sub` to it as well.

### Making a release

1. Set `better_crafty` in `app/config/version.json` (for example `1.1.0`),
   add a section to `CHANGELOG.md` if wanted, commit and push.
2. `git tag v1.1.0 && git push origin v1.1.0` (the tag must be `v` + the
   version, or the `docker` job stops with an error).
3. GitHub Actions runs the checks and publishes the image as `1.1.0`,
   `1.1` and `latest`.
4. On GitHub, Releases → Draft a new release → pick the tag, write what
   changed, Publish. Publishing it is what makes running panels show
   "Update Available!" (the check reads releases, not bare tags).

### Tests on GitHub (done)

`.github/workflows/ci.yml` ("Tests and Docker image"), on every push and
pull request except ones that change only `**.md` or `docs/**`:

- `lint`: `black --check app tests main.py` and `pylint app tests main.py`
  (tool versions pinned: black 26.5.1, pylint 4.1.3, pytest 9.1.1). To
  make pylint pass: renamed the `java_props` fixture
  (`@pytest.fixture(name=...)`), two `not x` instead of `x == []`, and two
  upstream chained comparisons (`backup_mgr.remove_old_backups`,
  `passkey_controller`), same behaviour.
- `tests`: pytest on Python 3.10, 3.11, 3.12, 3.13 and 3.14 (3.10 and 3.14
  checked here with `uv`: 170 pass).
- `commands`: `node dev/command-data/test_complete.js`.
- `startup`: starts Crafty with `--daemon --ignore`, waits for
  `/api/v2/crafty/check` to say ok, then expects `/login` to return 200 and
  `app/config/default-creds.txt` to exist (simulated here on a clean copy).
- `docker`: needs all four; runs on pushes to the default branch and on
  `v*` tags only. Publishes `ghcr.io/<owner>/better-crafty` always and
  `<DOCKERHUB_USERNAME>/better-crafty` when both secrets exist. Tags:
  `edge` for every default-branch push, `latest` + `X.Y.Z` + `X.Y` for a
  `vX.Y.Z` tag (so `latest` only moves on a release), `sha-<commit>`
  always. A tag that does not match `better_crafty` fails the job.
- Action versions are the newest majors as of 2026-10-17 (checkout,
  setup-python, setup-node v7; metadata-action v6; qemu, buildx, login v4;
  build-push v7), checked with actionlint 1.7.7. **Runs on GitHub pass**
  (`57ed1545` and `7bbdc549`: all nine jobs, image pushed to `ghcr.io`
  and Docker Hub).
- The browser tests in `dev/handoff-tools/` are not in CI (they need Java,
  the fake server and test data); run them by hand as before.
- The draft `dev/handoff-tools/docker-publish.yml` was removed.

### Error pop-ups (done)

- Every `bootbox` pop-up that showed the API's `error` / `error_data`
  (titles, messages, and plain `bootbox.alert(...)`) now passes it through
  `escapeHtml()`: 5 JS files and 26 templates, nearly all upstream code.
  A check that finds none left:
  `grep -rnE "(title|message): *[A-Za-z_.]+\.(error|error_data)\b" app/frontend --include=*.html --include=*.js | grep -v "escapeHtml\|/vendors/"`.
- `escapeHtml()` (`misc.js`) now takes `undefined`/`null` (gives `""`), so
  a missing error text cannot break a pop-up. The login page did not load
  `misc.js`; it does now (the password-reset answer is escaped too).
- The "MFA required" 403 (`base_handler.py`) used to send a link in
  `error_data`; it is now the plain warning text, because pages show
  `error_data` as text. The MFA page is linked from the warning in the
  user menu. The `otp.goToPage` translation is no longer used.
- Checked in the browser with a scratch script: the login reset answer
  and a terminal error containing `<img onerror=...>` show as text and run
  nothing; then `test_files`, `test_audit`, `test_backups`, `test_login`
  and `crawl.js` all pass.

### "Database is locked" (fixed, upstream bug)

- Seen during the browser tests: after `test_audit`, every save from the
  web pages (new backup, server settings) failed at once with
  `sqlite3.OperationalError: database is locked`, until Crafty restarted.
  The owner's real server would hit it too: the stats task writes every
  minute.
- Cause: `get_backups_by_server(model=True)` returned a lazy peewee cursor.
  The backup settings page (`/panel/edit_backup`) puts it in the page data
  and never reads it, and Tornado keeps template data alive until Python's
  garbage collector runs (the template namespace is a reference cycle). A
  half-read cursor keeps an SQLite read snapshot open on the web thread's
  connection, so once another thread writes, that connection's writes fail
  with `SQLITE_BUSY_SNAPSHOT` ("database is locked", no waiting).
- Fix: it returns a list (`app/classes/models/management.py`); every
  caller only loops over it or takes `len()`. Regression test
  `tests/classes/models/test_backups_query.py` fails with the old code.
- Checked for others: with the garbage collector turned off in the test
  Crafty (through `gdb`), `crawl.js` (every page) and the browser tests
  left no half-read cursor behind after the fix. API handlers do not
  have the problem (nothing keeps their data alive). Rule for new code:
  put lists or dicts, not query results, into page data.

### Restart with in-game warnings (done)

What the owner approved: "A restart action that warns players in the game
first ("Restarting in 5 minutes…"), which you could also schedule."

- **Panel:** the ⋮ menu next to Start/Restart/Stop has "Restart with
  warning…" (Java and Bedrock servers only: their console has `say`). It
  asks how long (1, 2, 5, 10, 15 or 30 minutes; 5 first), then a yellow
  bar under the buttons shows "Restarting in m:ss" with "Cancel restart".
  The bar is on every server sub page, follows the live stats, and comes
  back after a reload. At zero it goes away and the status shows
  "Restarting...".
- **In the game:** `say Restarting in 5 minutes.` at the start, then at
  30/15/10/5/2/1 minutes, 30 and 10 seconds, and each of the last five
  seconds. Cancel says `Restart cancelled.`
- **Nobody online:** it restarts at once (counted with the same ping as the
  Players tile). If the ping fails, it warns anyway. A stopped server is
  simply started, like the plain Restart button.
- **Ends a countdown:** Cancel, Stop, Kill, the plain Restart, an
  executable update, or the server stopping or crashing (checked before
  each warning). Starting a new warned restart replaces the old one.
- **Schedules:** choosing "Restart Server" shows "Warn players first"
  (No warning or one of the times). It is stored in the schedule's
  `action_id` (backups keep the backup id there), so no database change.
  The restart happens that long after the scheduled time.
- **API:** `POST /api/v2/servers/<id>/action/restart_server/<minutes>`
  answers `{"restart_in": seconds}` (0 = restarted at once; another
  minutes value gives 400 `INVALID_WARNING_TIME`).
  `POST .../action/cancel_restart` cancels (409 `NO_RESTART_PENDING` if
  there is none or the restart already began). `GET .../stats` and the
  live websocket stats carry `restart_in` (seconds, or null). The task API
  checks a restart's `action_id` too; it now also checks on PATCH (not
  only POST) that a backup schedule's id is one of this server's backups,
  and answers 405 `BACKUP_NOT_FOUND` instead of a server error for an
  unknown id.
- **How:** `app/classes/shared/restart_countdown.py` (a thread per
  countdown; a lock makes a Cancel in the last second either win or
  report "too late", never both). `ServerInstance` holds the current one
  (`start_restart_countdown`, `cancel_restart_countdown`,
  `restart_countdown_left`). The panel button calls the API directly; a
  schedule goes through the command queue (`tasks.command_watcher`).
  Counting the players pings the server (up to a few seconds), so the API
  handler does it off the web thread.
- **Not done (ideas):** a custom message, a warning before a scheduled
  stop, showing the warning time in the schedules list (it shows the
  action name only, as before).
- **Checked:** 21 unit tests (`tests/classes/shared/test_restart_countdown.py`,
  with a fake clock: warning times, cancel, stop, the last-second race,
  nobody online), and `dev/handoff-tools/test_restart_warned.js` (about 2
  minutes: dialog, banner, console text, reload, Cancel, Stop, a full one
  minute countdown that restarts the fake server, the schedule form, phone
  width). `test_server.js` and `crawl.js` still pass.

### Minecraft 26.1 save layout (players fixed)

Found while planning the world tools, by reading the 26.3 server jar (it is
no longer obfuscated): 26.1 moved files inside the world folder, and
converts older worlds the first time it loads them.

- Player files: `playerdata/`, `stats/`, `advancements/` became
  `players/data/`, `players/stats/`, `players/advancements/`. The Players
  tab looked only in the old folders, so it listed nobody on 26.x servers.
  `player_data.player_folder()` now uses the new folder when it exists.
  The keys inside the player files did not change. Test:
  `test_players_folder_of_minecraft_26`.
- Dimensions: `DIM-1` and `DIM1` became `dimensions/minecraft/the_nether`
  and `dimensions/minecraft/the_end`; the overworld's region files moved to
  `dimensions/minecraft/overworld`. World-level data moved out of
  `level.dat` into `data/minecraft/*.dat`, and the dragon fight is in
  `dimensions/minecraft/the_end/data/minecraft/ender_dragon_fight.dat`.
  The world tools (next) handle both layouts.

### Upstream (checked 2026-10-17)

- Upstream's newest release is still `v4.11.0` (`fe65b372`). Their `dev`
  branch has 21 commits towards 4.11.1 (Hytale bans format, a file manager
  speed-up, ANSI colours in the terminal, Bedrock NetherNet stats, a
  per-server ping mode with a database migration `20261005_ping_mode`).
- Not merged: it is unreleased, it has a database migration, and the
  terminal and config tab parts will conflict with this fork's changes.
  Merge when 4.11.1 is released (`git fetch upstream`, merge the tag,
  resolve conflicts, run every check and browser test), then bump
  `major`/`minor`/`sub` and release.

### Files (session 12)

- `app/classes/helpers/helpers.py`, `app/classes/shared/tasks.py`,
  `app/classes/web/panel_handler.py`, `server_handler.py`,
  `app/frontend/templates/footer.html`, `app/config/version.json`
- `.github/workflows/ci.yml` (new), `tests/classes/helpers/test_update_check.py`
  (new), `test_server_properties.py`, `test_command_data.py`,
  `app/classes/shared/backup_mgr.py`, `app/classes/controllers/passkey_controller.py`
- Pop-ups: `static/assets/js/shared/misc.js`, `files.js`, `editor.js`,
  `root-dir.js`, `userSettings.js`, `backupCodes.js`, 26 templates,
  `app/classes/web/base_handler.py`
- Database lock: `app/classes/models/management.py`,
  `tests/classes/models/test_backups_query.py` (new)
- 26.1 player folders: `app/classes/helpers/player_data.py`,
  `tests/classes/helpers/test_player_data.py`
- Warned restart: `app/classes/shared/restart_countdown.py` (new),
  `server.py`, `tasks.py`, `app/classes/controllers/servers_controller.py`,
  `app/classes/web/routes/api/servers/server/action.py`, `stats.py`,
  `tasks/index.py`, `tasks/task/index.py`,
  `templates/panel/parts/details_stats.html`, `server_schedule_edit.html`,
  `css/partial/crafty-server-overview.css`, `en_EN.json`,
  `tests/classes/shared/test_restart_countdown.py` (new),
  `dev/handoff-tools/test_restart_warned.js` (new)

## Development setup (any machine)

Written for Linux, macOS and Windows, but so far only run on Linux (the
cloud containers): if a step fails on the owner's PC, fix it and update this
section. Commands are for a terminal in the repo root. On Windows use
`python` and `.venv\Scripts\activate`.

### Needs

- Python 3.9 or newer (3.13 used so far), Git.
- Node.js 18 or newer (22 used so far), for the browser tests.
- Java 8 or newer on the PATH, for the fake Minecraft server in the tests.
- Docker Desktop, only for the session 6 Docker work.

### Python and the quick checks

```
python3 -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt pytest black pylint
pytest -q tests                 # 193 pass
black --check app tests
node dev/command-data/test_complete.js   # command suggestions engine, no browser
```

`pylint` uses the repo's `.pylintrc`. Since session 12 the whole code base
is clean and GitHub fails the build otherwise: `pylint app tests main.py`
must print no messages (about 40 seconds).

### Run Crafty from the checkout

```
python main.py -d -i
```

- Serves `https://localhost:8443` with a self-signed certificate. `-d`
  skips the interactive prompt; `-i` ignores a stale `session.lock`. Stop
  it with Ctrl+C.
- The first start writes `app/config/default-creds.txt` with the `admin`
  password. Everything Crafty creates (`servers/`, `backups/`, `logs/`,
  `import/`, `temp/`, the database) is already in `.gitignore`; this was
  checked on a fresh run.
- On Linux it refuses to run as root.
- **Templates are cached:** restart Crafty after editing anything in
  `app/frontend/templates/`. CSS and JS changes only need a browser reload.

### Test data

With Crafty running on a fresh checkout (no servers yet), in the same venv:

```
python dev/handoff-tools/setup_testdata.py
```

It reads the admin password from `default-creds.txt` (`--password` to give
it), and makes:

- two servers, "Survival World" and "Creative Build", imported from a zip
  of the fake server. It logs "Starting minecraft server version 1.21.1"
  and "Done", answers `list`, `say` and `stop`, and prints an error for
  anything else. Server 2 has no `logs/` folder on purpose.
- in server 1: `server.properties`, ban, op and whitelist files, a
  `logs/latest.log`, odd file names, 520 files in `many/`, and save files for
  five players (`player_fixtures.py`: modern and 1.12-era formats, and one
  with no known name).
- one backup of server 1.
- a role "Moderators" (id 1 on a fresh Crafty; `crawl.js` opens it).
- user `tester` / `TesterPass123` with 2FA.

It writes `token`, `mfa.json` and `local.json` in `dev/handoff-tools/`
(gitignored). Run it once per fresh Crafty; to start over, stop Crafty and
delete `servers/`, `backups/`, `import/` and `app/config/db/`, or use a new
clone. `--crafty-dir` and `--url` point it at a Crafty somewhere else.

By default some player, item, chat and file names contain HTML
(`<img onerror>`) for the escaping checks; `--no-xss` uses plain names (for
screenshots). Windows does not allow `<` and `>` in file names, so there the
HTML file name is skipped and the checks in `test_files.js` that look for it
fail; that is expected.

### Browser tests

```
cd dev/handoff-tools
npm install
npx playwright install chromium
node test_config.js
```

Each prints `PASS` or `FAIL` lines, and most save screenshots in
`dev/handoff-tools/shots/` (gitignored). The warning about
`NODE_TLS_REJECT_UNAUTHORIZED` is expected (self-signed certificate).
Settings come from `local.json`; the environment variables `CRAFTY_URL`,
`CRAFTY_DIR`, `CRAFTY_TOKEN`, `S1`, `S2`, `B1` and `CHROME` override them
(see `local.js`).

| Script | Checks |
|---|---|
| `test_login.js` | Login page: 2FA, backup codes, cooldown, redirects |
| `test_server.js` | Start, stop, kill and the Terminal on a running server |
| `test_complete.js`, `test_complete_phone.js` | Command suggestions in the Terminal (desktop, phone) |
| `test_config.js` | Config tab and the server.properties editor |
| `test_players.js` | Players tab: lists, ban, op, whitelist |
| `test_player_details.js` | Player details window without item pictures (prints results to read) |
| `test_item_icons.js` | Item pictures: game-style inventory, tooltip, contents, ender chest, phone, offer and progress (needs pictures, see Session 10) |
| `test_player_running.js` | Player actions on a running server (prints results to read) |
| `test_backups.js` | Backups tab |
| `test_files.js` | Files tab: rename, upload, escaping, many files |
| `test_logs.js` | Logs tab |
| `test_audit.js` | Schedule and webhook switches, restore errors, editor saves |
| `test_restart_warned.js` | Restart with in-game warnings: dialog, countdown, Cancel, schedules, phone (about 2 minutes; leaves server 1 running) |
| `crawl.js` | Opens every panel page (desktop and phone), reports page errors; `node crawl.js [substring]` |
| `chk_metrics.js` | Metrics chart zoom |
| `shot.js`, `panel.js`, `shot_files.js`, `shot_metrics.js`, `shot_header.js` | Screenshots only |
| `readme_shots.js` | README screenshots (see Session 5) |

Known noise, not bugs: 424 responses on the console (Crafty could not fetch
its news feed, e.g. without internet), ServiceWorker certificate errors
(self-signed certificate), and in `crawl.js` errors from the Ko-fi, Patreon
and GitLab widgets on the Credits, Contribute and similar pages (upstream,
third-party sites).

Notes:

- Login cooldown: 3 failed logins in 3 minutes lock the account for 5
  minutes, so do not run `test_login.js` twice back to back. It uses one
  of the 6 2FA backup codes per run and remembers the next one in
  `backup_idx`; after 5 runs make a fresh Crafty and run the setup again.
- The other scripts log in with the API token as a cookie, so they never
  touch the cooldown.
- `test_complete.js`, `test_server.js` and `test_player_running.js` start
  server 1 and stop it again.
- `start.sh`, `start_before.sh`, `stop.sh` and `sync.sh` are for the cloud
  containers of sessions 1-10 (a `crafty` user, `/home/crafty/run`). They
  are not needed on a PC.
