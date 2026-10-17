// World page: the facts, downloading the world (stopped and running), reset
// refused while running, resetting the End and the Nether, and phone width.
// world_fixtures.py writes the test world first and again at the end.
const L = require('./local');
const { chromium } = L;
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const TOKEN = L.token();
const S1 = L.S1;
const BASE = L.BASE;
const SERVER = path.join(L.RUN, 'servers', S1);
const PYTHON = process.platform === 'win32' ? 'python' : 'python3';
const python = (args) => execFileSync(PYTHON, args, { env: { ...process.env, REPO: path.resolve(__dirname, '../..') } }).toString().trim();
const fixtures = () => python([path.join(__dirname, 'world_fixtures.py'), SERVER]);
const zipNames = (file) => JSON.parse(python(['-c', 'import json, sys, zipfile; print(json.dumps(zipfile.ZipFile(sys.argv[1]).namelist()))', file]));
const hasDragonFight = () => python(['-c', 'import gzip, sys; print(b"DragonFight" in gzip.decompress(open(sys.argv[1], "rb").read()))', path.join(SERVER, 'world', 'level.dat')]) === 'True';

(async () => {
  const b = await chromium.launch(L.launchOptions);
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true, acceptDownloads: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errors = [];
  // The service worker fails on the self-signed certificate and the news
  // feed needs the internet; neither is about this page
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
  const stats = async () => (await api('GET', '/stats')).body.data;
  const consoleText = async () => (await api('GET', '/logs')).body.data.join('\n');
  const setRunning = async (running) => {
    if ((await stats()).running === running) return;
    await api('POST', running ? '/action/start_server' : '/action/stop_server');
    for (let i = 0; i < 30 && (await stats()).running !== running; i++) await p.waitForTimeout(1000);
  };
  const check = (ok, what) => console.log(`${ok ? 'PASS' : 'FAIL'} ${what}`);
  const page = `${BASE}/panel/server_detail?id=${S1}&subpage=world`;
  const cardText = (id) => p.$eval(`.world-dimension:has(button[data-dimension="${id}"])`, el => el.innerText);
  const resetButton = (id) => p.locator(`button[data-dimension="${id}"]`);
  const downloadDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'world-'));
  // The zip's address, to try it a second time
  let zipUrl = null;
  const download = async () => {
    const [file] = await Promise.all([
      p.waitForEvent('download', { timeout: 60000 }),
      p.click('#world_download_button'),
    ]);
    zipUrl = file.url();
    const target = path.join(downloadDir, file.suggestedFilename());
    await file.saveAs(target);
    return target;
  };

  await setRunning(false);
  fixtures();

  // API checks
  let r = await api('POST', '/world/reset', { dimension: 'overworld' });
  check(r.code === 400 && r.body.error === 'INVALID_DIMENSION', 'the overworld cannot be reset');
  r = await api('POST', '/world/reset', 'not json');
  check(r.code === 400 && r.body.error === 'INVALID_JSON', 'a body that is not JSON is refused');
  r = await api('GET', '/world/download/' + '0'.repeat(32));
  check(r.code === 404 && r.body.error === 'DOWNLOAD_NOT_FOUND', 'an unknown zip token is refused');
  r = await api('GET', '/world/download');
  check(r.code === 200 && r.body.data === null, 'no zip yet');

  // The page with the server stopped
  await p.goto(page, { waitUntil: 'networkidle' });
  await p.waitForSelector('#world_content:not(.d-none)');
  const facts = await p.$eval('#world_facts', el => el.innerText);
  check(facts.includes('1.21.4') && facts.includes('-4172144997902289642') && facts.includes('world'), 'version, seed and name shown');
  check(await p.$eval('.tab-simple-styled .nav-link.active', el => el.innerText.trim()) === 'World', 'World tab is active');
  check(await p.$$eval('.world-dimension', els => els.length) === 3, 'three dimensions');
  check((await p.$eval('.world-overworld', el => el.innerText)).includes('<img src=x'), 'odd player name shown as text');
  check(await p.evaluate(() => window.__xss2 === undefined), 'player name is not run as HTML');
  check((await cardText('the_end')).includes('jeb_'), 'the End lists the player who logged off there');
  check(!(await resetButton('the_end').isDisabled()) && !(await resetButton('the_nether').isDisabled()), 'reset buttons work while stopped');

  // Download while stopped
  let file = await download();
  let names = zipNames(file);
  check(/^[\w.-]+-world-\d{4}-\d\d-\d\d-\d{4}\.zip$/.test(path.basename(file)), 'zip name: ' + path.basename(file));
  check(['world/level.dat', 'world/region/r.0.0.mca', 'world/DIM-1/region/r.0.0.mca', 'world/DIM1/region/r.0.0.mca', 'world/playerdata/' + fs.readdirSync(path.join(SERVER, 'world', 'playerdata'))[0]].every(n => names.includes(n)), 'zip holds the world and its dimensions');
  check(!names.some(n => n.startsWith('server.properties') || n.startsWith('many/')), 'zip holds only the world');
  await p.waitForSelector('#world_status.alert-success');
  r = await api('GET', zipUrl.replace(`${BASE}/api/v2/servers/${S1}`, ''));
  check(r.code === 404, 'a zip downloads only once');
  check(!fs.existsSync(path.join(L.RUN, 'temp', 'world-downloads')) || fs.readdirSync(path.join(L.RUN, 'temp', 'world-downloads')).length === 0, 'the zip is deleted after the download');

  // Running: download saves first, reset is refused
  await setRunning(true);
  await p.reload({ waitUntil: 'networkidle' });
  await p.waitForSelector('#world_content:not(.d-none)');
  check(await resetButton('the_end').isDisabled(), 'reset disabled while running');
  check(await p.isVisible('#world_dimensions_note'), 'note says to stop the server');
  r = await api('POST', '/world/reset', { dimension: 'the_end' });
  check(r.code === 409 && r.body.error === 'SERVER_RUNNING', 'reset refused while running');
  const ready = p.waitForResponse(async res => /\/world\/download$/.test(res.url()) && res.request().method() === 'GET' && (await res.json()).data?.state === 'ready', { timeout: 60000 });
  const [readyResponse] = await Promise.all([ready, download().then(f => { file = f; })]);
  check((await readyResponse.json()).data.saved === true, 'the server saved before the zip');
  check(zipNames(file).includes('world/level.dat'), 'zip made while running');
  await p.waitForTimeout(1000);
  const text = await consoleText();
  check(/save-off|Automatic saving is now disabled/.test(text) && /Automatic saving is now enabled/.test(text), 'autosave held off and turned back on');

  // Stopping: the page notices on its own
  await setRunning(false);
  await p.waitForFunction(() => !document.querySelector('button[data-dimension="the_end"]').disabled, null, { timeout: 20000 });
  check(true, 'reset works again once stopped');

  // Reset the End: a confirmation that names the player
  await resetButton('the_end').click();
  await p.waitForSelector('.bootbox.show');
  const dialog = await p.$eval('.bootbox .modal-body', el => el.innerText);
  check(dialog.includes('jeb_') && dialog.includes('dragon'), 'dialog warns about the dragon and the player');
  check(await p.$eval('.world-reset-confirm', el => el.disabled), 'reset button off until ticked');
  await p.check('#world_reset_sure');
  await p.click('.world-reset-confirm');
  await p.waitForSelector('#world_status.alert-success');
  await p.waitForFunction(() => document.querySelector('.world-end').innerText.includes('Not made yet'));
  check(!fs.existsSync(path.join(SERVER, 'world', 'DIM1')), 'the End folder is gone');
  check(fs.existsSync(path.join(SERVER, 'world', 'DIM-1')), 'the Nether is kept');
  check(!hasDragonFight(), 'the dragon fight record is gone from level.dat');
  check(await resetButton('the_end').isDisabled(), 'nothing left to reset in the End');

  // Cancel leaves the Nether alone
  await resetButton('the_nether').click();
  await p.waitForSelector('.bootbox.show');
  await p.click('.bootbox .btn-secondary');
  await p.waitForSelector('.bootbox', { state: 'detached' });
  check(fs.existsSync(path.join(SERVER, 'world', 'DIM-1')), 'Cancel keeps the Nether');
  r = await api('POST', '/world/reset', { dimension: 'the_nether' });
  check(r.code === 200 && r.body.data.removed.join() === 'world/DIM-1', 'Nether reset through the API');
  r = await api('POST', '/world/reset', { dimension: 'the_nether' });
  check(r.code === 409 && r.body.error === 'NOTHING_TO_RESET', 'nothing left to reset in the Nether');
  // The two answers above are errors on purpose
  errors.splice(0, errors.length, ...errors.filter(e => !/world\/reset|world\/download\/0{32}|world\/download\/[0-9a-f]{32}/.test(e)));

  fixtures();
  await p.reload({ waitUntil: 'networkidle' });
  await p.waitForSelector('#world_content:not(.d-none)');
  await p.screenshot({ path: path.join(__dirname, 'shots', 'world.png'), fullPage: true });

  // Phone width
  const phone = await ctx.newPage();
  await phone.setViewportSize({ width: 390, height: 844 });
  phone.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) errors.push('PHONE ' + e.message); });
  await phone.goto(page, { waitUntil: 'networkidle' });
  await phone.waitForSelector('#world_content:not(.d-none)');
  const overflow = await phone.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(overflow <= 0, 'no sideways scrolling on a phone: ' + overflow);
  check(await phone.isVisible('#world_download_button'), 'download button on a phone');
  await phone.screenshot({ path: path.join(__dirname, 'shots', 'world_phone.png'), fullPage: true });

  check(errors.length === 0, 'no page errors: ' + JSON.stringify(errors));
  fs.rmSync(downloadDir, { recursive: true, force: true });
  await b.close();
})().catch(e => { console.error('FAIL', e); process.exit(1); });
