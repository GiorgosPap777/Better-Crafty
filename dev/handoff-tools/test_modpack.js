// New server from a modpack: the Modpack tab, the most downloaded list, Show
// more, search, choosing a pack and its version, refused requests, uploading
// a .mrpack (made here) and reading it, then building a small real Fabric
// pack ("Server Optimized" for 1.21.1) and checking its files. Phone width
// too. Needs the internet (api.modrinth.com, cdn.modrinth.com, Mojang and
// Fabric). Deletes the server it made at the end.
const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const TOKEN = L.token();
const BASE = L.BASE;
const SHOTS = process.env.SHOTS || path.join(__dirname, 'shots');
const PACK = 'ca0m6gMz'; // Server Optimized
const PACK_VERSION = 'MEznmVQB'; // v2-1.21.1

// A small .mrpack: one mod and one override file
function makePack(folder) {
  const file = path.join(folder, 'Test Pack 1.0.mrpack');
  const script = `
import hashlib, json, sys, zipfile
data = b"not a real mod"
index = {
    "formatVersion": 1, "game": "minecraft", "versionId": "1.0", "name": "Test Pack",
    "dependencies": {"minecraft": "1.21.1", "fabric-loader": "0.16.10"},
    "files": [
        {"path": "mods/test.jar", "hashes": {"sha1": hashlib.sha1(data).hexdigest(),
         "sha512": hashlib.sha512(data).hexdigest()}, "env": {"client": "required", "server": "required"},
         "downloads": ["https://cdn.modrinth.com/data/test/test.jar"], "fileSize": len(data)},
        {"path": "resourcepacks/look.zip", "hashes": {"sha1": "0" * 40, "sha512": "0" * 128},
         "downloads": ["https://cdn.modrinth.com/data/test/look.zip"], "fileSize": 5},
    ],
}
with zipfile.ZipFile(sys.argv[1], "w") as archive:
    archive.writestr("modrinth.index.json", json.dumps(index))
    archive.writestr("overrides/config/test.txt", "hello")
`;
  execFileSync('python3', ['-I', '-c', script, file]);
  return file;
}

(async () => {
  const b = await chromium.launch(L.launchOptions);
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errors = [];
  const allowed = /announcements|service-worker|favicon|modpacks\/(file|versions)\/\?(name=x|project_id=bad)/;
  p.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) errors.push('PAGEERROR ' + e.message); });
  p.on('console', m => { if (m.type() === 'error' && !/SSL|ServiceWorker|Failed to load resource/.test(m.text())) errors.push('CONSOLE ' + m.text()); });
  p.on('response', r => { if (r.status() >= 400 && !allowed.test(r.url())) errors.push(`${r.status()} ${r.url().replace(BASE, '')}`); });
  const auth = { headers: { Authorization: 'Bearer ' + TOKEN } };
  const api = async (method, url) => {
    const res = await p.request.fetch(`${BASE}${url}`, { method, ...auth });
    let body = null;
    try { body = await res.json(); } catch (e) { /* not JSON */ }
    return { code: res.status(), body };
  };
  let failed = 0;
  const check = (ok, what) => { console.log((ok ? 'ok   ' : 'FAIL ') + what); if (!ok) failed++; };

  // The tab is on the other wizard pages
  await p.goto(`${BASE}/server/step1`);
  check(await p.locator('.nav-link[href="/server/modpack_step1"]').count() === 1, 'the Java wizard has a Modpack tab');
  await p.goto(`${BASE}/server/modpack_step1`);
  check(await p.locator('.nav-link.active', { hasText: 'Modpack' }).count() === 1, 'the Modpack tab is open');
  await p.waitForSelector('#modpack_results .mods-row', { timeout: 30000 });
  check(/most downloaded/i.test(await p.textContent('#modpack_results_title')), 'lists the most downloaded first');
  const first = await p.locator('#modpack_results .mods-row').count();
  check(first > 10, `${first} packs on the first page`);
  check(await p.isDisabled('#modpack_build'), 'Build is off until a pack is chosen');
  await p.click('#modpack_more');
  await p.waitForFunction((n) => document.querySelectorAll('#modpack_results .mods-row').length > n, first, { timeout: 30000 });
  check(true, 'Show more adds packs');
  await p.screenshot({ path: path.join(SHOTS, 'modpack-popular.png') });

  // Refused requests
  check((await api('GET', '/api/v2/crafty/modpacks/file/?name=x.zip')).code === 400, 'refuses a file that is not .mrpack');
  check((await api('GET', '/api/v2/crafty/modpacks/file/?name=../../x.mrpack')).code === 400, 'refuses a path outside the upload folder');
  check((await api('GET', '/api/v2/crafty/modpacks/file/?name=missing.mrpack')).code === 404, 'says when the file is not there');
  check((await api('GET', '/api/v2/crafty/modpacks/versions/?project_id=bad/id')).code === 400, 'refuses a bad project id');

  // Search and choose
  await p.fill('#modpack_query', 'Server Optimized');
  await p.click('#modpack_search_form button[type=submit]');
  const row = p.locator(`#modpack_results .mods-row:has(.modpack-choose[data-project="${PACK}"])`);
  await row.waitFor({ timeout: 30000 });
  check(true, 'search finds Server Optimized');
  await row.locator('.modpack-choose').click();
  await p.waitForSelector('#modpack_version_group:not(.d-none)', { timeout: 30000 });
  check((await row.locator('.modpack-choose').textContent()).trim() === 'Chosen', 'the button says Chosen');
  check(/Server Optimized/.test(await p.textContent('#modpack_chosen')), 'shows the chosen pack');
  check(/Server Optimized/.test(await p.inputValue('#modpack_name')), 'fills in the server name');
  const options = await p.locator('#modpack_version option').count();
  check(options > 1, `${options} versions to pick from`);
  check(/Minecraft .*Fabric/.test(await p.locator('#modpack_version option').first().textContent()), 'versions show Minecraft and the loader');
  check(!await p.isDisabled('#modpack_build'), 'Build is on');
  await p.selectOption('#modpack_version', PACK_VERSION);
  await p.screenshot({ path: path.join(SHOTS, 'modpack-chosen.png') });

  // Upload a .mrpack and read it
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'modpack-'));
  const packFile = makePack(folder);
  await p.setInputFiles('#modpack_file', packFile);
  await p.click('#modpack_upload_button');
  await p.waitForFunction(() => /Test Pack/.test(document.querySelector('#modpack_chosen')?.textContent || ''), null, { timeout: 30000 });
  const facts = await p.textContent('#modpack_chosen');
  console.log('     ' + facts.trim());
  check(/Minecraft 1\.21\.1 · Fabric 0\.16\.10 · 1 files/.test(facts), 'shows what is in the uploaded pack');
  check(/1 files are only for players/.test(await p.textContent('#modpack_status')), 'says what is left out');
  check(await p.isHidden('#modpack_version_group'), 'no version list for an upload');
  check(/Server Optimized/.test(await p.inputValue('#modpack_name')) === false, 'the name follows the new pack');
  check((await row.locator('.modpack-choose').textContent()).trim() === 'Choose', 'the Modrinth pack is no longer chosen');
  fs.rmSync(folder, { recursive: true, force: true });
  const uploaded = path.join(L.RUN, 'import', 'upload', 'Test Pack 1.0.mrpack');
  check(fs.existsSync(uploaded), 'the upload is in the import folder');
  fs.rmSync(uploaded, { force: true });

  // Phone width
  await p.setViewportSize({ width: 390, height: 844 });
  await p.goto(`${BASE}/server/modpack_step1`);
  await p.waitForSelector('#modpack_results .mods-row', { timeout: 30000 });
  const wide = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  check(!wide, 'no sideways scrolling at phone width');
  await p.screenshot({ path: path.join(SHOTS, 'modpack-phone.png') });
  await p.locator('#modpack_results .modpack-choose').first().click();
  await p.waitForSelector('#modpack_version_group:not(.d-none)', { timeout: 30000 });
  await p.waitForTimeout(800);
  const top = await p.evaluate(() => document.getElementById('modpack_settings').getBoundingClientRect().top);
  check(top < 200, 'choosing on a phone scrolls to the settings');
  await p.screenshot({ path: path.join(SHOTS, 'modpack-phone-chosen.png') });

  // Build the small Fabric pack
  await p.setViewportSize({ width: 1440, height: 900 });
  await p.goto(`${BASE}/server/modpack_step1`);
  await p.fill('#modpack_query', 'Server Optimized');
  await p.click('#modpack_search_form button[type=submit]');
  await row.waitFor({ timeout: 30000 });
  await row.locator('.modpack-choose').click();
  await p.waitForSelector('#modpack_version_group:not(.d-none)', { timeout: 30000 });
  await p.selectOption('#modpack_version', PACK_VERSION);
  await p.fill('#modpack_name', 'Modpack test');
  await p.fill('#modpack_mem_min', '1');
  await p.fill('#modpack_mem_max', '2');
  await p.fill('#modpack_port', '25601');
  await p.click('#modpack_build');
  await p.waitForURL(/server_detail\?id=.*subpage=term/, { timeout: 30000 });
  const serverId = new URL(p.url()).searchParams.get('id');
  check(true, 'opens the new server\'s Terminal');
  let done = null;
  for (let i = 0; i < 90 && !done; i++) {
    await p.waitForTimeout(2000);
    const text = await p.textContent('#virt_console').catch(() => '');
    if (/The modpack is installed|could not be installed/.test(text)) done = text;
  }
  console.log('     ' + (done || '').split(/\n|(?<=\S)(?=Downloading|Java|Copying)/).slice(0, 12).join('\n     '));
  check(/The modpack is installed/.test(done || ''), 'the Terminal says the modpack is installed');
  await p.screenshot({ path: path.join(SHOTS, 'modpack-terminal.png') });
  const server = (await api('GET', `/api/v2/servers/${serverId}`)).body.data;
  const root = server.path;
  const mods = fs.readdirSync(path.join(root, 'mods')).filter(f => f.endsWith('.jar'));
  check(mods.length > 0, `${mods.length} mods downloaded`);
  check(/^fabric-server-mc\.1\.21\.1-loader\./.test(server.executable), 'runs the Fabric launcher: ' + server.executable);
  check(/-Xms1024M -Xmx2048M -jar fabric-server/.test(server.execution_command) && / nogui$/.test(server.execution_command), 'the command has the memory: ' + server.execution_command);
  check(/java-21|^java /.test(server.execution_command), 'uses Java 21 when it is there');
  check(/server-port=25601/.test(fs.readFileSync(path.join(root, 'server.properties'), 'utf8')), 'sets the port');
  check(/eula=false/.test(fs.readFileSync(path.join(root, 'eula.txt'), 'utf8')), 'leaves the EULA for the first start');
  check(fs.existsSync(path.join(root, 'crafty-modpack.json')), 'records where the pack came from');
  check(!fs.existsSync(path.join(root, '.crafty-modpack.mrpack')), 'removes the downloaded pack');
  check(!fs.readdirSync(root).some(f => f.endsWith('.part')), 'no half-downloaded files left');
  check((await api('DELETE', `/api/v2/servers/${serverId}?files=true`)).code === 200, 'deletes the test server');

  check(errors.length === 0, 'no page errors' + (errors.length ? ': ' + errors.join(' | ') : ''));
  await b.close();
  console.log(failed ? `${failed} FAILED` : 'all passed');
  process.exit(failed ? 1 : 0);
})();
