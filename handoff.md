# Better Crafty: handoff notes

Read this first when picking the work back up. It records what has been done,
what is half done, and how to rebuild the test setup (the cloud container is
temporary, so only what is committed here survives).

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

### Questions still waiting on the owner

- Should a PR to `main` be opened? (Explained what it means; not opened.)
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
| (this commit) | README for visitors with before/after screenshots |

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
  `$SP/venv/bin/python -c "from tornado.template import Loader;
  Loader('app/frontend/templates').load('panel/X.html')"`.
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
  1. Make an upstream copy:
     `cp -a /home/crafty/run /home/crafty/run_before`, then
     `git archive fe65b372 | tar -x -C /home/crafty/run_before` (fe65b372 is
     the plain Crafty 4.11.0 commit), `chown -R crafty:crafty` it.
  2. Stop the fork, start the copy with `start_before.sh`, run
     `node readme_shots.js before <dir>`; then stop it, start the fork with
     `start.sh` and run `node readme_shots.js after <dir>`. Start server 1
     first in both so the header shows live numbers.
  3. Both start scripts unset `JAVA_TOOL_OPTIONS`/`JDK_JAVA_OPTIONS`: in the
     cloud sandbox Java prints them into the console, which would put
     sandbox details into the Terminal screenshots. Look at every image
     before committing it.
  4. Use clean test data (normal player names and files); the XSS test
     files and players look odd in a README.
  5. Shrink: `convert X.png -strip -define png:compression-level=9`, and
     JPEG (`-quality 84`) for the login shots (photo background).

## Rebuilding the test setup

The helper scripts are saved in `dev/handoff-tools/`. They expect to live in
the session scratchpad (`SP`), next to a `venv/`, a `token` file and a
`shots/` folder, so copy them there first:
`cp dev/handoff-tools/* "$SP"/ && mkdir -p "$SP/shots"`.

1. Crafty refuses to run as root: create a `crafty` user. Run copy in
   `/home/crafty/run`, venv in `/home/crafty/venv`
   (`pip install -r requirements.txt`; if the venv was built as root,
   `chmod -R o+rX` it).
2. `sync.sh` copies tracked repo files into the run dir (keeps config,
   servers, logs). `start.sh` (run it in the background) starts Crafty on
   `https://localhost:8443`; `stop.sh` stops it. **Templates are cached:**
   after editing a template, run stop, sync, start. CSS/JS only needs sync.
3. Linters/tests: a separate venv in `$SP/venv` with black, pylint, pytest,
   pyotp, requests. Run `black --check app tests` and `pytest -q tests`
   (104 passing at this commit).
4. Browser tests use Playwright at `/opt/node22/lib/node_modules/playwright`
   with Chromium at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`.
   - `crawl.js`: opens every panel page (desktop + mobile) and reports page
     errors and failed requests. `node crawl.js [substring]`.
   - `test_login.js`: login E2E (2FA, backup codes, cooldown, redirects).
     Uses `mfa.json` and a `backup_idx` file (next unused backup code).
     Login cooldown is 3 failures / 3 minutes, then 5 minutes locked, so
     don't run it twice back to back. **All checks passed** at this commit.
   - `test_server.js`: start/stop/kill and console on a running server.
   - `shot.js`, `panel.js`, `shot_files.js`, `shot_metrics.js`,
     `shot_header.js`: screenshots. `chk_metrics.js`: metrics zoom checks.
   - `test_config.js`, `test_players.js`, `test_backups.js`,
     `test_files.js`, `test_logs.js`, `test_audit.js`: E2E checks for each
     tab (`test_audit.js` covers the session 4 fixes). Run with
     `NODE_TLS_REJECT_UNAUTHORIZED=0 node X.js`.
   - After `test_files.js`, rename `world/data/renamed.txt` back to
     `world.txt` and delete `κόσμος.txt` in server 1.
5. Test data to recreate (ids will change; update the constants at the top
   of the scripts): admin API token in `$SP/token`; two servers made with
   "import server" from a zip containing a fake Java jar (server 2 has no
   `logs` folder on purpose; server 1 has a `logs/latest.log` with an
   HTML-looking chat line for the XSS check) (the "custom"
   server type is a stub upstream); a user `tester` / `TesterPass123`
   (id 3) with TOTP, set up by `mk_mfa_user.py "$SP"`; a role; a backup.
   Panel screenshots log in with the token cookie to avoid the login
   cooldown.
