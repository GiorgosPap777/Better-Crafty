// Off-site backups: the Off-site storage page (add, test, edit, refuse,
// remove), a backup's off-site copy (choose, copy now, bring back), the line
// on the Backups tab, and phone width. Uses a folder place in a new temporary
// folder. Set S3_ENDPOINT, S3_BUCKET, S3_KEY and S3_SECRET to also add an
// S3-compatible place (a local MinIO, versitygw or RustFS will do).
const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const os = require('os');
const path = require('path');
const TOKEN = L.token();
const S1 = L.S1;
const B1 = L.B1;
const BASE = L.BASE;
const BACKUPS = path.join(L.RUN, 'backups', S1, B1);
const S3 = process.env.S3_ENDPOINT ? {
  endpoint: process.env.S3_ENDPOINT, bucket: process.env.S3_BUCKET, key: process.env.S3_KEY, secret: process.env.S3_SECRET,
} : null;

(async () => {
  // Crafty may run as another user, so everyone may write here
  const disk = fs.mkdtempSync(path.join(os.tmpdir(), 'offsite-'));
  fs.chmodSync(disk, 0o777);
  const b = await chromium.launch(L.launchOptions);
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) errors.push('PAGEERROR ' + e.message); });
  p.on('console', m => { if (m.type() === 'error' && !/SSL|ServiceWorker|Failed to load resource/.test(m.text())) errors.push('CONSOLE ' + m.text()); });
  p.on('response', r => {
    // 400s the test asks for on purpose are checked where they happen
    if (r.status() >= 400 && !/announcements|service-worker|favicon|\/api\/v2\/crafty\/offsite/.test(r.url())) errors.push(`${r.status()} ${r.url().replace(BASE, '')}`);
  });
  const auth = { headers: { Authorization: 'Bearer ' + TOKEN } };
  const api = async (method, url, data) => {
    const res = await p.request.fetch(`${BASE}/api/v2${url}`, { method, ...auth, data });
    let body = null;
    try { body = await res.json(); } catch (e) { /* not JSON */ }
    return { code: res.status(), body };
  };
  const offsiteUrl = `/servers/${S1}/backups/backup/${B1}/offsite`;
  const before = (await api('GET', offsiteUrl)).body.data;
  const check = (ok, what) => console.log(`${ok ? 'PASS' : 'FAIL'} ${what}`);
  const card = (name) => p.locator('.offsite-place', { has: p.locator('h4', { hasText: name }) });
  // A page at phone width, opened fresh so the panel lays itself out for it
  const phoneShot = async (url, ready, file, part) => {
    const phone = await b.newContext({ viewport: { width: 390, height: 844 }, ignoreHTTPSErrors: true });
    await phone.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
    const page = await phone.newPage();
    await page.goto(BASE + url, { waitUntil: 'networkidle' });
    await page.waitForSelector(ready);
    const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
    const target = path.join(__dirname, 'shots', file);
    await (part ? page.locator(part).screenshot({ path: target }) : page.screenshot({ path: target, fullPage: true }));
    await phone.close();
    return fits;
  };

  // The Off-site storage page
  await p.goto(`${BASE}/panel/offsite`, { waitUntil: 'networkidle' });
  check((await p.locator('.nav-link.active').innerText()).includes('Off-site storage'), 'Off-site storage tab is shown and active');
  await p.click('#offsite_add');
  await p.waitForSelector('#offsite_modal.show');
  check(await p.locator('#offsite_path').isVisible() && !(await p.locator('#offsite_endpoint').isVisible()), 'adding starts with a folder');
  await p.fill('#offsite_name', 'Disk <b>1</b>');
  await p.fill('#offsite_path', path.join(BACKUPS, 'copies'));
  await p.click('#offsite_form_save');
  await p.waitForSelector('#offsite_form_status:not(.d-none)');
  check((await p.locator('#offsite_form_status').innerText()).includes('That is where the backups are made'), 'a folder inside the backups is refused');
  await p.fill('#offsite_path', disk);
  await p.click('#offsite_form_test');
  await p.waitForFunction(() => /It works/.test(document.querySelector('#offsite_form_status').innerText));
  check(true, 'Test in the form works');
  await p.click('#offsite_form_save');
  await p.waitForSelector('#offsite_modal', { state: 'hidden' });
  await card('Disk <b>1</b>').waitFor();
  check(await p.locator('.offsite-place h4 b').count() === 0, 'the name is shown as text');
  check((await card('Disk <b>1</b>').innerText()).includes(disk), 'the card says where the copies go');
  check(fs.existsSync(path.join(disk, '.better-crafty-offsite')), 'the test left the marker file');
  const status = await p.locator('#offsite_status').innerText();
  check(!status || /same disk/.test(status), 'a same-disk warning, if any, is shown: ' + status);
  await card('Disk <b>1</b>').locator('.offsite-test').click();
  await p.waitForFunction(() => [...document.querySelectorAll('.offsite-test-result')].some(el => /It works/.test(el.innerText)));
  check(true, 'Test on the card works');
  await card('Disk <b>1</b>').locator('.offsite-edit').click();
  await p.waitForSelector('#offsite_modal.show');
  check((await p.locator('#offsite_modal_title').innerText()) === 'Edit Disk <b>1</b>', 'editing shows the name as text');
  check((await p.inputValue('#offsite_path')) === disk, 'editing fills in the folder');
  await p.fill('#offsite_name', 'Test disk');
  await p.click('#offsite_form_save');
  await p.waitForSelector('#offsite_modal', { state: 'hidden' });
  await card('Test disk').waitFor();
  check(true, 'renamed');

  let s3Name = null;
  if (S3) {
    s3Name = 'Test cloud';
    await p.click('#offsite_add');
    await p.waitForSelector('#offsite_modal.show');
    await p.click('label[for=offsite_kind_s3]');
    check(await p.locator('#offsite_endpoint').isVisible() && !(await p.locator('#offsite_path').isVisible()), 'S3 shows its own fields');
    await p.fill('#offsite_name', s3Name);
    await p.fill('#offsite_endpoint', S3.endpoint);
    await p.fill('#offsite_bucket', S3.bucket);
    await p.fill('#offsite_prefix', 'better crafty test');
    await p.fill('#offsite_access_key', S3.key);
    await p.fill('#offsite_secret_key', S3.secret + 'x');
    await p.click('#offsite_form_save');
    await p.waitForSelector('#offsite_form_status:not(.d-none)');
    check((await p.locator('#offsite_form_status').innerText()).includes('The secret key is wrong'), 'a wrong secret key is explained');
    await p.fill('#offsite_secret_key', S3.secret);
    await p.click('#offsite_form_save');
    await p.waitForSelector('#offsite_modal', { state: 'hidden' });
    await card(s3Name).waitFor();
    await card(s3Name).locator('.offsite-edit').click();
    await p.waitForSelector('#offsite_modal.show');
    check(await p.locator('#offsite_secret_saved').isVisible() && (await p.inputValue('#offsite_secret_key')) === '', 'the secret key stays on the server');
    await p.click('#offsite_form_save');
    await p.waitForSelector('#offsite_modal', { state: 'hidden' });
    check(true, 'saving again keeps the secret key');
  }

  check(await phoneShot('/panel/offsite', '.offsite-place', 'offsite_phone.png'), 'Off-site storage page fits a phone');
  await p.screenshot({ path: path.join(__dirname, 'shots', 'offsite.png') });

  // A backup's off-site copy
  const places = (await api('GET', '/crafty/offsite/')).body.data;
  const diskPlace = places.find(place => place.name === 'Test disk');
  await p.goto(`${BASE}/panel/edit_backup?id=${S1}&backup_id=${B1}`, { waitUntil: 'networkidle' });
  await p.waitForSelector('#offsite_target');
  await p.selectOption('#offsite_target', diskPlace.target_id);
  await p.waitForFunction(() => document.querySelector('#offsite_saved') && /Saved/.test(document.querySelector('#offsite_saved').innerText));
  check((await p.locator('#offsite_section').innerText()).includes('Nothing copied yet.'), 'nothing copied yet');
  await p.fill('#offsite_keep', '2');
  await p.locator('#offsite_keep').dispatchEvent('change');
  await p.waitForFunction(() => /Saved/.test(document.querySelector('#offsite_saved').innerText));
  check((await api('GET', offsiteUrl)).body.data.offsite_keep === 2, 'the number of copies to keep is saved');
  await p.click('#offsite_copy_now');
  await p.waitForFunction(() => /was copied/.test(document.querySelector('#offsite_section').innerText), null, { timeout: 60000 });
  await p.waitForSelector('.offsite-copy-list li');
  const newest = fs.readdirSync(BACKUPS).filter(name => name.endsWith('.zip')).sort().pop();
  const copied = fs.readdirSync(path.join(disk, B1));
  check(copied.length === 1 && copied[0].endsWith('_' + newest), 'the newest backup was copied: ' + copied.join(', '));
  check((await p.locator('.offsite-copy-list li').first().innerText()).includes('Also here'), 'a copy that is also here says so');

  // Bring it back after losing it here
  const aside = path.join(disk, 'aside.bin');
  fs.renameSync(path.join(BACKUPS, newest), aside);
  await p.reload({ waitUntil: 'networkidle' });
  await p.waitForSelector('.offsite-fetch');
  const reloaded = p.waitForEvent('framenavigated', { timeout: 60000 });
  await p.locator('.offsite-fetch').first().click();
  await reloaded;
  await p.waitForSelector('.offsite-copy-list li');
  const back = path.join(BACKUPS, newest);
  check(fs.existsSync(back) && fs.readFileSync(back).equals(fs.readFileSync(aside)), 'the copy came back with the same bytes');
  check((await p.locator('#backup_table').innerText()).includes(newest), 'it is in the list of backups again');
  fs.unlinkSync(aside);

  check(await phoneShot(`/panel/edit_backup?id=${S1}&backup_id=${B1}`, '.offsite-copy-list li', 'offsite_backup_phone.png', '#offsite_section'),
    'backup settings page fits a phone');
  await p.locator('#offsite_section').screenshot({ path: path.join(__dirname, 'shots', 'offsite_backup.png') });

  // The Backups tab
  await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=backup`, { waitUntil: 'networkidle' });
  const facts = (await p.locator('.backup-plan', { hasText: 'Default Backup' }).locator('.backup-facts').innerText()).replace(/\s+/g, ' ');
  check(/Off-site copy Test disk · copied .*ago/i.test(facts), 'the Backups tab shows the off-site copy: ' + facts);

  // A new backup cannot be copied until it is saved
  await p.goto(`${BASE}/panel/add_backup?id=${S1}`, { waitUntil: 'networkidle' });
  check((await p.locator('#offsite_section').innerText()).includes('Save this backup first'), 'a new backup says to save it first');

  // Removing the places
  await p.goto(`${BASE}/panel/offsite`, { waitUntil: 'networkidle' });
  await card('Test disk').waitFor();
  check((await card('Test disk').innerText()).includes('Used by 1 backup'), 'the card says it is used');
  await card('Test disk').locator('.offsite-delete').click();
  await p.waitForSelector('.bootbox.show');
  check((await p.locator('.bootbox .modal-title').innerText()) === 'Remove Test disk?', 'removing asks first');
  check((await p.locator('.bootbox-body').innerText()).includes('1 backup copies there'), 'and says what stops');
  await p.click('.bootbox .btn-danger');
  await card('Test disk').waitFor({ state: 'detached' });
  check((await api('GET', offsiteUrl)).body.data.offsite_id === '', 'the backup stopped copying there');
  check(fs.readdirSync(path.join(disk, B1)).length === 1, 'the copies stay');
  if (s3Name) {
    await card(s3Name).locator('.offsite-delete').click();
    await p.waitForSelector('.bootbox.show');
    await p.click('.bootbox .btn-danger');
    await card(s3Name).waitFor({ state: 'detached' });
  }

  // Put the backup's settings back as they were
  await api('PATCH', offsiteUrl, { offsite_id: before.offsite_id, offsite_keep: before.offsite_keep });
  fs.rmSync(disk, { recursive: true, force: true });
  check(errors.length === 0, 'no page errors' + (errors.length ? ': ' + errors.join(' | ') : ''));
  await b.close();
})().catch(e => { console.log('FAIL ' + e.stack); process.exit(1); });
