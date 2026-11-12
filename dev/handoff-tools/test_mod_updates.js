// Update notices: an older Chunky jar in plugins/ shows a badge on the
// dashboard and a number on the Mods tab; updating it on the Mods tab clears
// both. Then a scheduled "Update mods and plugins" task, run now, backs the
// server up and updates the jar; the schedule list names the action in
// words; phone width. Needs the internet (api.modrinth.com and
// cdn.modrinth.com). Puts the plugins folder back as it was at the end.
const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const TOKEN = L.token();
const S1 = L.S1;
const BASE = L.BASE;
const SERVER = path.join(L.RUN, 'servers', S1);
const PLUGINS = path.join(SERVER, 'plugins');
const SHOTS = process.env.SHOTS || path.join(__dirname, 'shots');
const VERSION = '1.21.4';

(async () => {
  const hadPlugins = fs.existsSync(PLUGINS);
  const keep = hadPlugins ? fs.readdirSync(PLUGINS) : [];
  const b = await chromium.launch(L.launchOptions);
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  // The Mods tab shows this server as Paper 1.21.4
  await ctx.addInitScript(([key, choice]) => {
    try { localStorage.setItem(key, choice); } catch (e) { /* private window */ }
  }, [`better-crafty-mods-${S1}`, JSON.stringify({ platform: 'paper', game_version: VERSION })]);
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) errors.push('PAGEERROR ' + e.message); });
  p.on('console', m => { if (m.type() === 'error' && !/SSL|ServiceWorker|Failed to load resource/.test(m.text())) errors.push('CONSOLE ' + m.text()); });
  p.on('response', r => { if (r.status() >= 400 && !/announcements|service-worker|favicon/.test(r.url())) errors.push(`${r.status()} ${r.url().replace(BASE, '')}`); });
  const auth = { headers: { Authorization: 'Bearer ' + TOKEN } };
  const api = async (method, url, data) => {
    const res = await p.request.fetch(`${BASE}/api/v2/servers/${S1}${url}`, { method, ...auth, data });
    let body = null;
    try { body = await res.json(); } catch (e) { /* not JSON */ }
    return { code: res.status(), body };
  };
  let failed = 0;
  const check = (ok, what) => { console.log((ok ? 'ok   ' : 'FAIL ') + what); if (!ok) failed++; };
  const owner = fs.statSync(SERVER);

  // The oldest Chunky for Paper 1.21.4, put in plugins/ as if by hand
  const modrinth = (url) => execFileSync('curl', ['-sSfL', '-A', 'GiorgosPap777/Better-Crafty tests', url], { maxBuffer: 64 << 20 });
  const query = `loaders=${encodeURIComponent('["paper","bukkit"]')}&game_versions=${encodeURIComponent(`["${VERSION}"]`)}`;
  const versions = JSON.parse(modrinth(`https://api.modrinth.com/v2/project/chunky/version?${query}`));
  const old = versions[versions.length - 1].files.find(f => f.primary) || versions[versions.length - 1].files[0];
  const oldJar = modrinth(old.url);
  const putOldJar = () => {
    fs.mkdirSync(PLUGINS, { recursive: true });
    fs.readdirSync(PLUGINS).forEach(f => fs.rmSync(path.join(PLUGINS, f), { recursive: true, force: true }));
    fs.writeFileSync(path.join(PLUGINS, old.filename), oldJar);
    fs.chownSync(PLUGINS, owner.uid, owner.gid);
    fs.chownSync(path.join(PLUGINS, old.filename), owner.uid, owner.gid);
  };
  const jars = () => fs.readdirSync(PLUGINS).filter(f => f.endsWith('.jar'));
  putOldJar();
  console.log('     old jar: ' + old.filename);

  // The Mods tab's list keeps the result for the badge
  const listed = (await api('GET', `/modrinth?platform=paper&game_version=${VERSION}`)).body.data;
  check(listed.update_count === 1, `the Mods list says 1 update (${listed.update_count})`);

  // Dashboard badge
  const badge = `tr[id="${S1}"] .dash-mod-updates`;
  await p.goto(`${BASE}/panel/dashboard`);
  await p.waitForSelector(badge, { timeout: 30000 });
  check((await p.textContent(badge)).trim().startsWith('1'), 'the dashboard badge says 1');
  check(/subpage=mods$/.test(await p.getAttribute(badge, 'href')), 'the badge opens the Mods tab');
  const title = await p.getAttribute(badge, 'title');
  check(/^Updates on Modrinth: Chunky \(.+ → .+\)$/.test(title), 'the badge names the update: ' + title);
  await p.screenshot({ path: path.join(SHOTS, 'mod-updates-dashboard.png'), clip: { x: 0, y: 0, width: 1440, height: 700 } });

  // The number on the Mods tab, and updating it there
  await p.click(badge);
  await p.waitForSelector('#mods_installed .mods-row', { timeout: 60000 });
  const tabCount = '.server-tabs .nav-link[href$="subpage=mods"] .tab-count';
  check((await p.textContent(tabCount)).trim().startsWith('1'), 'the Mods tab says 1');
  await p.screenshot({ path: path.join(SHOTS, 'mod-updates-tab.png'), clip: { x: 0, y: 0, width: 1440, height: 600 } });
  await p.locator('#mods_installed .mods-action', { hasText: 'Update to' }).click();
  await p.waitForSelector('#mods_status.alert-success:has-text("Installed")', { timeout: 120000 });
  await p.waitForFunction((sel) => !document.querySelector(sel), tabCount, { timeout: 30000 });
  check(true, 'updating on the Mods tab clears the number');
  check(!jars().includes(old.filename), 'the old jar was replaced: ' + jars().join(', '));
  await p.goto(`${BASE}/panel/dashboard`);
  await p.waitForSelector(`tr[id="${S1}"]`, { timeout: 30000 });
  check(await p.locator(badge).count() === 0, 'and the dashboard badge is gone');

  // A turned off jar is not counted (an update would turn it on)
  putOldJar();
  fs.renameSync(path.join(PLUGINS, old.filename), path.join(PLUGINS, old.filename + '.disabled'));
  check((await api('GET', `/modrinth?platform=paper&game_version=${VERSION}`)).body.data.update_count === 0, 'a turned off jar is not counted');

  // Phone width with the badge
  putOldJar();
  await api('GET', `/modrinth?platform=paper&game_version=${VERSION}`);
  await p.setViewportSize({ width: 390, height: 844 });
  await p.goto(`${BASE}/panel/dashboard`);
  const cardBadge = `.dash-card:has(a[href="/panel/server_detail?id=${S1}"]) .dash-mod-updates`;
  await p.waitForSelector(cardBadge, { timeout: 30000 });
  check(await p.isVisible(cardBadge), 'the badge is on the phone card');
  const wide = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(wide <= 0, `no sideways scrolling at phone width (${wide})`);
  await p.screenshot({ path: path.join(SHOTS, 'mod-updates-phone.png') });
  await p.setViewportSize({ width: 1440, height: 900 });

  // A scheduled "Update mods and plugins"
  await p.goto(`${BASE}/panel/add_schedule?id=${S1}`);
  await p.waitForSelector('#action', { timeout: 30000 });
  check(await p.isHidden('#ifUpdateMods'), 'the explanation is hidden at first');
  await p.selectOption('#action', 'update_mods');
  check(/default backup/.test(await p.textContent('#ifUpdateMods')) && await p.isVisible('#ifUpdateMods'), 'choosing it explains what it does');
  await p.fill('#name_input', 'Mod updates test');
  await p.fill('#interval', '1');
  await p.selectOption('#interval_type', 'days');
  await p.fill('#time', '05:00');
  await p.click('#new_schedule_form button[type=submit]');
  await p.waitForURL(/subpage=schedules/, { timeout: 30000 });
  check(/Update mods and plugins/.test(await p.textContent('body')), 'the schedule list names the action in words');
  await p.screenshot({ path: path.join(SHOTS, 'mod-updates-schedules.png'), fullPage: true });
  const task = (await api('GET', '/tasks')).body.data.find(t => t.name === 'Mod updates test');
  check(task && task.command === 'update_mods_server', 'the task runs update_mods_server');

  const backupDir = path.join(L.RUN, 'backups', S1);
  const backupsBefore = fs.existsSync(backupDir) ? fs.readdirSync(backupDir, { recursive: true }) : [];
  const run = await api('POST', `/tasks/${task.schedule_id}/run`);
  check(run.code === 200, `run now (${run.code})`);
  const start = Date.now();
  while (jars().includes(old.filename) && Date.now() - start < 180000) {
    await new Promise(r => setTimeout(r, 2000));
  }
  check(!jars().includes(old.filename), 'the task updated the jar: ' + jars().join(', '));
  const backupsAfter = fs.existsSync(backupDir) ? fs.readdirSync(backupDir, { recursive: true }) : [];
  const made = backupsAfter.filter(f => !backupsBefore.includes(f) && /\.zip$/.test(f));
  check(made.length === 1, 'it made a backup first: ' + made.join(', '));
  await new Promise(r => setTimeout(r, 3000));
  check((await api('GET', `/modrinth?platform=paper&game_version=${VERSION}`)).body.data.update_count === 0, 'nothing left to update');

  // Run again with nothing to update: no new backup
  const before = fs.readdirSync(backupDir, { recursive: true }).length;
  await api('POST', `/tasks/${task.schedule_id}/run`);
  await new Promise(r => setTimeout(r, 8000));
  check(fs.readdirSync(backupDir, { recursive: true }).length === before, 'with nothing to update it makes no backup');

  // Clean up: the task, the backup it made, the plugins folder
  check((await api('DELETE', `/tasks/${task.schedule_id}`)).code === 200, 'task removed');
  made.forEach(f => fs.rmSync(path.join(backupDir, f), { force: true }));
  fs.readdirSync(PLUGINS).filter(f => !keep.includes(f)).forEach(f => fs.rmSync(path.join(PLUGINS, f), { recursive: true, force: true }));
  if (!hadPlugins) fs.rmSync(PLUGINS, { recursive: true, force: true });
  await api('GET', `/modrinth?platform=paper&game_version=${VERSION}`);

  check(errors.length === 0, 'no page errors' + (errors.length ? ': ' + errors.join(' | ') : ''));
  await b.close();
  console.log(failed ? `${failed} FAILED` : 'all passed');
  process.exit(failed ? 1 : 0);
})();
