// Data packs on the Mods tab: a server whose type is not found (vanilla)
// opens on Data packs, entering the Minecraft version, the most downloaded
// list, refused requests, installing Terralith into world/datapacks,
// turning it off and on, an older version from the Versions list and its
// update, a pack folder made by hand, removing both, switching to Mods and
// plugins and back, and phone width. Needs the internet (api.modrinth.com
// and cdn.modrinth.com). Removes the datapacks folder it made at the end.
const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const path = require('path');
const TOKEN = L.token();
const S1 = L.S1;
const BASE = L.BASE;
const SERVER = path.join(L.RUN, 'servers', S1);
const PACKS = path.join(SERVER, 'world', 'datapacks');
const SHOTS = process.env.SHOTS || path.join(__dirname, 'shots');
const TERRALITH = 'terralith';

(async () => {
  const hadPacks = fs.existsSync(PACKS);
  const b = await chromium.launch(L.launchOptions);
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
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
  const status = () => p.textContent('#mods_status');
  // Clear the message before each action, so the wait sees the new one
  const clearStatus = () => p.evaluate(() => { document.querySelector('#mods_status').textContent = ''; });
  const waitStatus = (re) => p.waitForFunction((src) => new RegExp(src).test(document.querySelector('#mods_status').textContent), re.source, { timeout: 60000 });
  const files = () => (fs.existsSync(PACKS) ? fs.readdirSync(PACKS).sort() : []);
  const installedRow = (text) => p.locator('#mods_installed .mods-row', { hasText: text });

  check((await api('GET', '/modrinth')).body.data.supported === false, 'the test server\'s type is not found (like vanilla)');
  await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=mods`);
  await p.waitForFunction(() => document.querySelector('#mods_title').textContent === 'Data packs', null, { timeout: 30000 });
  await p.waitForSelector('#mods_content:not(.d-none)', { timeout: 30000 });
  check(true, 'opens on Data packs');
  check(await p.locator('.mods-kinds .btn.active', { hasText: 'Data packs' }).count() === 1, 'the Data packs button is on');
  check(/world\/datapacks\//.test(await p.textContent('#mods_target')), 'shows the world\'s datapacks folder');
  check(/vanilla too/.test(await p.textContent('#mods_note')), 'says data packs work on every Java server');
  check(/version is unknown/.test(await p.textContent('#mods_note')), 'says the Minecraft version is unknown');
  check(/Search data packs/.test(await p.getAttribute('#mods_query', 'placeholder')), 'the search is for data packs');

  // Enter the version
  await p.click('.mods-fact-button .btn');
  check(await p.isHidden('#mods_platform_label'), 'only the version is asked');
  await p.fill('#mods_game_version', '1.21.1');
  await p.click('#mods_choose button[type=submit]');
  await p.waitForSelector('#mods_results .mods-row', { timeout: 30000 });
  check(/1\.21\.1/.test(await p.textContent('#mods_target')), 'shows Minecraft 1.21.1');
  check(/most downloaded data packs/i.test(await p.textContent('#mods_results_title')), 'lists the most downloaded data packs');
  check(await p.locator('#mods_results .mods-row').count() === 20, '20 results');
  check(/make a backup/.test(await p.textContent('#mods_modrinth_note')), 'the note is about data packs');
  await p.screenshot({ path: path.join(SHOTS, 'datapacks-popular.png') });

  // Refused requests
  check((await api('POST', '/datapacks/pack', { file: '../server.properties', action: 'remove' })).code === 404, 'refuses a file outside the datapacks folder');
  check((await api('POST', '/datapacks/pack', { file: 'x.zip', action: 'delete' })).code === 400, 'refuses an unknown action');
  check((await api('GET', '/datapacks/versions?project_id=bad/id&game_version=1.21.1')).code === 400, 'refuses a bad project id');
  check((await api('POST', '/datapacks/install', { project_id: TERRALITH, version_id: 'bad/id', game_version: '1.21.1' })).code === 400, 'refuses a bad version id');
  check((await api('GET', '/datapacks?game_version=1.21.1;x')).code === 400, 'refuses a bad Minecraft version');

  // Install Terralith
  await p.fill('#mods_query', 'Terralith');
  await p.click('#mods_search_form button[type=submit]');
  const row = p.locator(`#mods_results .mods-row:has(a[href$="/project/${TERRALITH}"])`);
  await row.waitFor({ timeout: 30000 });
  await clearStatus();
  await row.locator('.mods-action', { hasText: 'Install' }).click();
  await waitStatus(/Installed Terralith/);
  console.log('     ' + (await status()).trim());
  check(/uses the new data packs when it starts/.test(await status()), 'says the server uses it when it starts');
  const zip = files().find(f => /^Terralith.*\.zip$/.test(f));
  check(!!zip, 'the zip is in world/datapacks: ' + files().join(', '));
  check(await row.locator('.mods-done').count() === 1, 'the result says Installed');
  check(/Terralith/.test(await p.textContent('#mods_installed')), 'listed as installed by name');
  await p.screenshot({ path: path.join(SHOTS, 'datapacks-installed.png') });

  // Off and on
  await clearStatus();
  await installedRow('Terralith').locator('.mods-action', { hasText: 'Turn off' }).click();
  await waitStatus(/Turned off/);
  check(files().includes(zip + '.disabled'), 'turned off: renamed .zip.disabled');
  check(/Turned off/.test(await installedRow('Terralith').textContent()), 'shows Turned off');
  await clearStatus();
  await installedRow('Terralith').locator('.mods-action', { hasText: 'Turn on' }).click();
  await waitStatus(/Turned on/);
  check(files().includes(zip), 'turned on again');

  // An older version, then its update
  await installedRow('Terralith').locator('.mods-versions').click();
  await p.waitForSelector('.mods-version-select', { timeout: 30000 });
  const options = await p.locator('.mods-version-select option').count();
  check(options > 1, `${options} versions to choose from`);
  await p.selectOption('.mods-version-select', { index: 1 });
  await clearStatus();
  await p.click('.mods-version-install');
  await waitStatus(/Installed Terralith/);
  const older = files().find(f => /^Terralith.*\.zip$/.test(f));
  check(older && older !== zip && files().length === 1, `the older zip replaced the newer one: ${older}`);
  const update = installedRow('Terralith').locator('.mods-action', { hasText: 'Update to' });
  check(await update.count() === 1, 'offers the update');
  await clearStatus();
  await update.click();
  await waitStatus(/Installed Terralith/);
  check(files().join() === zip, 'updated back to the newest');

  // A pack folder made by hand
  fs.mkdirSync(path.join(PACKS, 'handmade', 'data'), { recursive: true });
  fs.writeFileSync(path.join(PACKS, 'handmade', 'pack.mcmeta'), '{"pack": {"pack_format": 48, "description": "x"}}');
  // Crafty must be able to remove it, as it could a folder it made itself
  const owner = fs.statSync(SERVER);
  for (const made of ['handmade', 'handmade/data', 'handmade/pack.mcmeta']) {
    fs.chownSync(path.join(PACKS, made), owner.uid, owner.gid);
  }
  await p.reload();
  await p.waitForSelector('#mods_installed .mods-row', { timeout: 30000 });
  const folderRow = installedRow('handmade');
  check(/Folder/.test(await folderRow.textContent()), 'a pack folder is listed as a folder');
  check(await folderRow.locator('.mods-action', { hasText: 'Turn off' }).count() === 0, 'a folder cannot be turned off');
  await folderRow.locator('.btn-outline-danger').click();
  await p.waitForSelector('.mods-remove-confirm', { timeout: 10000 });
  check(/world\/datapacks/.test(await p.textContent('.bootbox-body')), 'the remove dialog names the folder');
  await clearStatus();
  await p.click('.mods-remove-confirm');
  await waitStatus(/Removed handmade/);
  check(!fs.existsSync(path.join(PACKS, 'handmade')), 'the folder is removed');
  await installedRow('Terralith').locator('.btn-outline-danger').click();
  await clearStatus();
  await p.click('.mods-remove-confirm');
  await waitStatus(/Removed Terralith/);
  check(files().length === 0, 'the zip is removed');

  // Mods and plugins, and back
  await p.click('.mods-kinds .btn[data-kind="jar"]');
  await p.waitForFunction(() => document.querySelector('#mods_title').textContent === 'Mods and plugins', null, { timeout: 30000 });
  await p.waitForSelector('#mods_choose:not(.d-none)', { timeout: 30000 });
  check(await p.isVisible('#mods_platform_label'), 'Mods and plugins asks for the server type');
  check(/can use data packs/.test(await p.textContent('#mods_note')), 'and points to data packs');
  await p.reload();
  await p.waitForSelector('#mods_choose:not(.d-none)', { timeout: 30000 });
  check(await p.textContent('#mods_title') === 'Mods and plugins', 'the choice is kept');
  await p.click('#mods_note .btn-link');
  await p.waitForSelector('#mods_results .mods-row', { timeout: 30000 });
  check(await p.textContent('#mods_title') === 'Data packs', 'the link in the note opens Data packs');

  // Phone width
  await p.setViewportSize({ width: 390, height: 844 });
  await p.reload();
  await p.waitForSelector('#mods_results .mods-row', { timeout: 30000 });
  const wide = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  check(!wide, 'no sideways scrolling at phone width');
  await p.screenshot({ path: path.join(SHOTS, 'datapacks-phone.png'), fullPage: true });

  if (!hadPacks) fs.rmSync(PACKS, { recursive: true, force: true });
  check(errors.length === 0, 'no page errors' + (errors.length ? ': ' + errors.join(' | ') : ''));
  await b.close();
  console.log(failed ? `${failed} FAILED` : 'all passed');
  process.exit(failed ? 1 : 0);
})();
