# Better Crafty: handoff notes

Read this first when picking the work back up. It records what has been done,
what is half done, and how to rebuild the test setup (the cloud container is
temporary, so only what is committed here survives).

## The project

- A fork of **Crafty Controller 4.11.0** (Python Tornado + peewee/SQLite;
  jQuery + Bootstrap 4.3.1 + bootbox front end; Phosphor icons).
- Repo: `giorgospap777/better-crafty`. **All work is on branch
  `claude/login-server-admin-improvements-ctbqdu`.** `main` is empty.
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

### Questions still waiting on the owner

- Which login bugs had they actually seen? (We fixed every one we found, but
  never heard which ones they meant.)
- Should a PR to `main` be opened?
- What next: dashboard redesign, file manager, backups/schedules, renaming
  the product to "Better Crafty"?

## Commits so far

| Commit | What |
|---|---|
| `d3946c3f` | Login screen fixes and redesign |
| `360b0f92` | Server administration pages (shared server header, console) |
| (this commit) | UI pass 2: fixes across dashboard, settings, users, wizards, plus this handoff |

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

### 3. UI pass 2 (this commit)

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

## Unfinished: next steps, in order

Found by an audit of the server tabs. Each was checked by reading the code;
the ones marked **confirmed** are real.

1. **Stored XSS (confirmed), fix first.** File and folder names go into
   `innerHTML` unescaped, so a file named `<img src=x onerror=...>` runs
   script for whoever opens the page.
   - `panel/server_backup_edit.html` ~710-724, `process_tree_response`
     (`${dpath}`, `${filename}`).
   - `panel/server_backup.html` ~434-449, same function.
   - `static/assets/js/shared/files.js`: upload dialog title ~452
     (`${path}`), delete title ~582 (`${path}`), unzip row ~648
     (`${name}`), upload progress ~734 (`${file.name}`).
   - Plan: add a small `escapeHtml()` (`& < > " '`) and wrap each value.
     Attribute values decode entities, so `data-path` still holds the real
     path. Note `id="${dpath}"` is also used as a lookup key; check
     `getDirView`/`getElementById` callers still work.
2. `files.js`: rows added by "load more" (~199-202) get no click handlers;
   file names use `encodeURI` (~305) and `editor.js:3` decodes twice; rename
   uses `.replace(oldName, newName)` on the whole path (~392), which breaks
   when the name also appears in a parent folder; `hideUploadBox` is
   undefined (~459); delete dialog labels read `attr("")` (~496/500/587/591);
   ~126-139 doesn't check `res.ok`; upload headers break on non-Latin-1 names.
3. Same JSON replacer bug as the wizards in `server_backup_edit.html`
   ~384-401, `server_schedule_edit.html` ~221-240, `server_webhook_edit.html`
   ~155-176 (also empty trigger becomes 0), `server_config.html` ~524-534.
4. False success messages: schedule/webhook enable toggles don't update data
   attributes or check the response; `server_admin_controls.html`
   ban/kick/unban ignore `status` (the API returns 200 with
   `status: "error"`); `server_schedules.html:444` checks
   `statusText === "OK"`; server delete in `server_config.html` ignores
   failures; restore spinner not closed on error; snapshot restore has no
   confirmation.
5. `server_backup_edit.html:426` unguarded `webSocket.on` (crashes on HTTP).
6. Double submits: editor Ctrl+S, "backup now" button.
7. `server_logs.html` filter words inserted as HTML;
   `server_config.html:130` port `max="65566"` (should be 65535).

Then: restart Crafty, run the crawl, `test_server.js`, black and pytest,
commit, push, report to the owner.

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
- `show_errors` defaults to true, so tracebacks reach the browser. Upstream
  choice; worth raising with the owner.

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
   (79 passing at this commit).
4. Browser tests use Playwright at `/opt/node22/lib/node_modules/playwright`
   with Chromium at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`.
   - `crawl.js`: opens every panel page (desktop + mobile) and reports page
     errors and failed requests. `node crawl.js [substring]`.
   - `test_login.js`: login E2E (2FA, backup codes, cooldown, redirects).
     Uses `mfa.json` and a `backup_idx` file (next unused backup code).
     Login cooldown is 3 failures / 3 minutes, then 5 minutes locked, so
     don't run it twice back to back. **All checks passed** at this commit.
   - `test_server.js`: start/stop/kill and console on a running server.
   - `shot.js`, `panel.js`: screenshots.
5. Test data to recreate (ids will change; update the constants at the top
   of the scripts): admin API token in `$SP/token`; two servers made with
   "import server" from a zip containing a fake Java jar (the "custom"
   server type is a stub upstream); a user `tester` / `TesterPass123`
   (id 3) with TOTP, set up by `mk_mfa_user.py "$SP"`; a role; a backup.
   Panel screenshots log in with the token cookie to avoid the login
   cooldown.
