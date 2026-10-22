// Mods page: choosing the server type when it is not found, the most
// downloaded list, a search, installing a plugin from Modrinth, turning it
// off and on, removing it, refused requests, updating two old jars with
// Update all, and phone width. Needs the internet (api.modrinth.com and
// cdn.modrinth.com). Removes the plugins folder it made at the end.
const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const { execFileSync } = require('child_process');
const path = require('path');
const TOKEN = L.token();
const S1 = L.S1;
const BASE = L.BASE;
const SERVER = path.join(L.RUN, 'servers', S1);
const SHOTS = process.env.SHOTS || path.join(__dirname, 'shots');

(async () => {
  const hadPlugins = fs.existsSync(path.join(SERVER, 'plugins'));
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

  await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=mods`);
  await p.waitForSelector('#mods_content:not(.d-none)', { timeout: 30000 });
  check(await p.locator('.nav-link.active', { hasText: 'Mods' }).count() === 1, 'the Mods tab is open');
  const detected = (await api('GET', '/modrinth')).body.data;
  console.log('     detected:', detected.platform || 'nothing', detected.game_version || '');
  if (!detected.supported) {
    check(await p.isVisible('#mods_choose'), 'asks for the server type when it is not found');
    check(/could not tell/.test(await p.textContent('#mods_note')), 'says why');
  } else {
    await p.click('.mods-fact-button .btn');
  }
  await p.selectOption('#mods_platform', 'paper');
  await p.fill('#mods_game_version', '1.21.4');
  await p.click('#mods_choose button[type=submit]');
  await p.waitForSelector('#mods_results .mods-row', { timeout: 30000 });
  check(/Paper/.test(await p.textContent('#mods_target')) && /1\.21\.4/.test(await p.textContent('#mods_target')), 'shows Paper 1.21.4');
  check(/most downloaded/i.test(await p.textContent('#mods_results_title')), 'lists the most downloaded first');
  check(await p.locator('#mods_results .mods-row').count() === 20, '20 results');
  await p.click('#mods_more');
  await p.waitForFunction(() => document.querySelectorAll('#mods_results .mods-row').length === 40, null, { timeout: 30000 });
  check(true, 'Show more adds 20');
  await p.screenshot({ path: path.join(SHOTS, 'mods-popular.png'), fullPage: true });

  await p.fill('#mods_query', 'luckperms');
  await p.click('#mods_search_form button[type=submit]');
  await p.waitForFunction(() => /LuckPerms/.test(document.querySelector('#mods_results .mods-row .mods-name')?.textContent || ''), null, { timeout: 30000 });
  check(true, 'search finds LuckPerms first');
  const button = p.locator('#mods_results .mods-row').first().locator('.mods-action');
  await button.click();
  await p.waitForSelector('#mods_status.alert-success', { timeout: 120000 });
  const status = await p.textContent('#mods_status');
  console.log('     ' + status);
  check(/Installed LuckPerms-Bukkit-.*\.jar/.test(status), 'says what was installed');
  check((await button.textContent()).trim() === 'Installed' && await button.isDisabled(), 'the button says Installed');
  check(/LuckPerms/.test(await p.textContent('#mods_installed')), 'the installed list shows it');
  const jars = fs.readdirSync(path.join(SERVER, 'plugins')).filter(f => f.endsWith('.jar'));
  check(jars.length === 1 && /^LuckPerms-Bukkit-/.test(jars[0]), 'the jar is in plugins/');
  await p.screenshot({ path: path.join(SHOTS, 'mods-installed.png'), fullPage: true });

  // Turn it off, on again, then remove it
  const row = p.locator('#mods_installed .mods-row').first();
  await row.locator('button', { hasText: 'Turn off' }).click();
  await p.waitForSelector('#mods_status:has-text("Turned off")', { timeout: 30000 });
  let files = fs.readdirSync(path.join(SERVER, 'plugins'));
  check(files.length === 1 && files[0] === jars[0] + '.disabled', 'Turn off renames it to .jar.disabled');
  check(/Turned off/.test(await p.textContent('#mods_installed')), 'the list says it is turned off');
  await p.locator('#mods_installed .mods-row').first().locator('button', { hasText: 'Turn on' }).click();
  await p.waitForSelector('#mods_status:has-text("Turned on")', { timeout: 30000 });
  files = fs.readdirSync(path.join(SERVER, 'plugins'));
  check(files.length === 1 && files[0] === jars[0], 'Turn on gives it its name back');
  await p.locator('#mods_installed .mods-row').first().locator('.btn-outline-danger').click();
  await p.waitForSelector('.mods-remove-confirm', { timeout: 10000 });
  check(/Remove LuckPerms-Bukkit-/.test(await p.textContent('.modal-title')), 'asks before removing');
  await p.click('.mods-remove-confirm');
  await p.waitForSelector('#mods_status:has-text("Removed")', { timeout: 30000 });
  check(fs.readdirSync(path.join(SERVER, 'plugins')).length === 0, 'Remove deletes the jar');
  check(/Nothing in the plugins folder/.test(await p.textContent('#mods_installed')), 'the list is empty again');
  await p.waitForFunction(() => /Install/.test(document.querySelector('#mods_results .mods-row .mods-action')?.textContent || ''), null, { timeout: 30000 });
  check((await p.locator('#mods_results .mods-row').first().locator('.mods-action').textContent()).trim() === 'Install', 'the search result can be installed again');
  const outside = await api('POST', '/modrinth/jar', { file: '../server.properties', action: 'remove', platform: 'paper' });
  check(outside.code === 404 && outside.body.error === 'FILE_NOT_FOUND', 'refused: a file outside the folder');
  check(fs.existsSync(path.join(SERVER, 'server.properties')), 'server.properties is still there');
  await p.locator('#mods_results .mods-row').first().locator('.mods-action').click();
  await p.waitForSelector('#mods_status:has-text("Installed")', { timeout: 120000 });

  const again = await api('POST', '/modrinth/install', { project_id: 'luckperms', platform: 'paper', game_version: '1.21.4' });
  check(again.code === 200 && again.body.data.installed[0].up_to_date === true, 'installing it again changes nothing');
  const listed = (await api('GET', '/modrinth?platform=paper&game_version=1.21.4')).body.data.installed;
  check(listed.length === 1 && listed[0].title === 'LuckPerms' && listed[0].update === null, 'the API lists it, no update');
  const bad = [
    [await api('POST', '/modrinth/install', { project_id: '../../x', platform: 'paper' }), 400, 'INVALID_PROJECT'],
    [await api('POST', '/modrinth/install', { project_id: 'luckperms', platform: 'nukkit' }), 400, 'INVALID_PLATFORM'],
    [await api('POST', '/modrinth/install', { project_id: 'luckperms', platform: 'paper', game_version: '1.21; rm' }), 400, 'INVALID_VERSION'],
    [await api('POST', '/modrinth/install', { project_id: 'luckperms', platform: 'paper', game_version: '1.2' }), 404, 'NO_COMPATIBLE_VERSION'],
    [await api('GET', '/modrinth/search?offset=x&platform=paper'), 400, 'INVALID_OFFSET'],
  ];
  bad.forEach(([res, code, error]) => check(res.code === code && res.body.error === error, `refused: ${error}`));
  errors.splice(0, errors.length, ...errors.filter(e => !/^(400|404) \/api\/v2\/servers\/[^/]+\/modrinth/.test(e)));

  // Update all: older LuckPerms and Chunky jars in plugins/ get both updated
  const modrinth = (url) => execFileSync('curl', ['-sSfL', '-A', 'GiorgosPap777/Better-Crafty tests', url], { maxBuffer: 64 << 20 });
  const oldest = (slug) => {
    const query = `loaders=${encodeURIComponent('["paper","bukkit"]')}&game_versions=${encodeURIComponent('["1.21.4"]')}`;
    const versions = JSON.parse(modrinth(`https://api.modrinth.com/v2/project/${slug}/version?${query}`));
    const old = versions[versions.length - 1];
    return old.files.find(f => f.primary) || old.files[0];
  };
  const plugins = path.join(SERVER, 'plugins');
  fs.readdirSync(plugins).forEach(f => fs.rmSync(path.join(plugins, f), { recursive: true, force: true }));
  const oldJars = ['luckperms', 'chunky'].map(slug => {
    const file = oldest(slug);
    fs.writeFileSync(path.join(plugins, file.filename), modrinth(file.url));
    return file.filename;
  });
  console.log('     old jars:', oldJars.join(', '));
  await p.reload();
  await p.waitForSelector('.mods-update-all', { timeout: 60000 });
  check((await p.textContent('.mods-update-all')).trim() === 'Update all (2)', 'offers Update all (2)');
  check(await p.locator('#mods_installed button', { hasText: 'Update to' }).count() === 2, 'each jar has its own Update button');
  await p.click('.mods-update-all');
  await p.waitForSelector('#mods_status.alert-success:has-text("Installed")', { timeout: 180000 });
  console.log('     ' + await p.textContent('#mods_status'));
  const newJars = fs.readdirSync(plugins).filter(f => f.endsWith('.jar'));
  check(newJars.length === 2 && !newJars.some(f => oldJars.includes(f)), 'both jars were replaced by new ones');
  check(await p.locator('.mods-update-all').count() === 0, 'no Update all button after updating');
  await p.screenshot({ path: path.join(SHOTS, 'mods-updated.png'), fullPage: true });

  await p.setViewportSize({ width: 390, height: 844 });
  await p.reload();
  await p.waitForSelector('#mods_content:not(.d-none)', { timeout: 30000 });
  await p.waitForTimeout(1500);
  const wide = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(wide <= 0, `no sideways scrolling at phone width (${wide})`);
  await p.screenshot({ path: path.join(SHOTS, 'mods-phone.png'), fullPage: true });

  if (!hadPlugins) fs.rmSync(path.join(SERVER, 'plugins'), { recursive: true, force: true });
  check(errors.length === 0, 'no page errors' + (errors.length ? ': ' + errors.join(' | ') : ''));
  await b.close();
  console.log(failed ? `${failed} failed` : 'all passed');
  process.exit(failed ? 1 : 0);
})();
