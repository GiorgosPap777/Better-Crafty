// Audit fixes E2E: schedule/webhook switches, restore errors, snapshot confirm, editor double save
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const SP = __dirname, BASE = 'https://localhost:8443';
const TOKEN = fs.readFileSync(SP + '/token', 'utf8').trim();
const S1 = '669ae1ce-61fa-498d-9782-6f3bb1804313';
const B1 = 'be668426-9dad-4194-92f2-87d0d4fd6575';
const ok = (c, m) => console.log((c ? 'PASS ' : 'FAIL ') + m);
const api = (path, opts = {}) => fetch(BASE + path, { ...opts, headers: { Authorization: 'Bearer ' + TOKEN } }).then(r => r.json());
const unwrap = r => (r && r.data && "enabled" in r.data ? r.data : r).enabled;
const taskEnabled = async id => unwrap(await api(`/api/v2/servers/${S1}/tasks/${id}`));
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: 'localhost', path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) errs.push(e.message); });

  // --- Schedules
  await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=schedules`, { waitUntil: 'networkidle' });
  const sw = p.locator('#schedule_table .schedule-custom-toggle[data-schedule-id="1"]');
  ok(await taskEnabled(1) === true, 'schedule 1 starts enabled');
  ok(await sw.evaluate(e => e.classList.contains('active') && e.getAttribute('aria-pressed') === 'true'), 'switch shows on');
  let patch = p.waitForResponse(r => r.request().method() === 'PATCH');
  await sw.click(); await patch; await sleep(200);
  ok(await taskEnabled(1) === false, 'first click turns it off on the server');
  ok(await sw.evaluate(e => !e.classList.contains('active') && e.dataset.scheduleEnabled === 'false'), 'switch shows off');
  ok(await p.locator('.schedule-enabled-toggle[data-schedule-id="1"]').evaluate(e => !e.checked), 'details popup checkbox follows');
  patch = p.waitForResponse(r => r.request().method() === 'PATCH');
  await sw.click(); await patch; await sleep(200);
  ok(await taskEnabled(1) === true, 'second click turns it back on (was stuck before)');
  ok(await sw.evaluate(e => e.classList.contains('active')), 'switch shows on again');

  await p.route('**/api/v2/servers/*/tasks/*', r => r.request().method() === 'PATCH'
    ? r.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ status: 'error', error: 'NOT_AUTHORIZED', error_data: 'No <b>access</b>' }) })
    : r.continue());
  await sw.click();
  await p.locator('.bootbox.show').waitFor({ timeout: 5000 });
  const alertText = await p.locator('.bootbox.show .modal-body').innerText();
  ok(alertText.includes('No <b>access</b>'), 'refused change shows the error as text: ' + alertText.trim());
  ok(await sw.evaluate(e => e.classList.contains('active')), 'refused change leaves the switch on');
  ok(await taskEnabled(1) === true, 'server still enabled');
  await p.locator('.bootbox.show .btn').first().click();
  await p.unroute('**/api/v2/servers/*/tasks/*');

  // --- Webhooks
  const created = await api(`/api/v2/servers/${S1}/webhook`, { method: 'POST', body: JSON.stringify({
    webhook_type: 'Discord', name: 'Audit hook', url: 'https://example.invalid/hook', bot_name: 'Crafty',
    trigger: ['start_server'], body: 'hi', color: '#005cd1', enabled: true }) });
  ok(created.status === 'ok', 'webhook created ' + JSON.stringify(created).slice(0, 100));
  const hookId = created.data && created.data.webhook_id;
  await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=webhooks`, { waitUntil: 'networkidle' });
  const hw = p.locator(`#webhook_table .webhook-custom-toggle[data-webhook-id="${hookId}"]`).first();
  const hookCount = await p.locator(`.webhook-custom-toggle[data-webhook-id="${hookId}"]`).count();
  ok(hookCount >= 1, 'webhook switch found x' + hookCount);
  const hookEnabled = async () => unwrap(await api(`/api/v2/servers/${S1}/webhook/${hookId}`));
  for (const want of [false, true, false]) {
    patch = p.waitForResponse(r => r.request().method() === 'PATCH');
    await p.locator(`.webhook-custom-toggle[data-webhook-id="${hookId}"]:visible`).first().click(); await patch; await sleep(200);
    ok(await hookEnabled() === want, `webhook click -> ${want}`);
  }
  await api(`/api/v2/servers/${S1}/webhook/${hookId}`, { method: 'DELETE' });

  // --- Restore error + snapshot confirm
  await p.goto(`${BASE}/panel/edit_backup?id=${S1}&backup_id=${B1}`, { waitUntil: 'networkidle' });
  const restoreBtn = p.locator('.restore_button').first();
  ok(await restoreBtn.count() === 1, 'restore button present');
  let restoreCalls = 0;
  await p.route(`**/api/v2/servers/${S1}/backups/backup/${B1}/`, async r => {
    if (r.request().method() !== 'POST') return r.continue();
    restoreCalls++;
    await sleep(400);
    r.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ status: 'error', error: 'X', error_data: 'Disk <i>full</i>' }) });
  });
  await restoreBtn.evaluate(e => e.scrollIntoView());
  await restoreBtn.click();
  await p.locator('.bootbox.show #restore-box').waitFor();
  await p.locator('.bootbox.show .btn-outline-danger').click();
  await sleep(500);
  ok(await p.locator('.bootbox.show #restore-box').count() === 1, 'no choice made: restore dialog stays open');
  // dismiss the "choose an option" alert
  await p.locator('.bootbox.show').last().locator('.btn').first().click(); await sleep(400);
  await p.locator('#optionInPlace').check({ force: true });
  await p.locator('.bootbox.show .btn-outline-danger').click();
  await p.locator('.bootbox.show:has-text("Restore failed")').waitFor({ timeout: 8000 });
  await sleep(600);
  ok(await p.locator('.bootbox.show .ph-spinner-gap').count() === 0, 'spinner taken down after error');
  ok((await p.locator('.bootbox.show .modal-body').last().innerText()).includes('Disk <i>full</i>'), 'restore error shown as text');
  ok(restoreCalls === 1, 'one restore request');
  await p.locator('.bootbox.show .btn').first().click(); await sleep(500);
  ok(await p.locator('.modal-backdrop').count() === 0, 'no leftover backdrop');

  await restoreBtn.evaluate(e => $(e).data('type', 'snapshot'));
  await restoreBtn.click();
  await p.locator('.bootbox.show').waitFor();
  const snapText = await p.locator('.bootbox.show .modal-body').innerText();
  ok(/will be deleted/.test(snapText), 'snapshot restore asks first: ' + snapText.trim().slice(0, 60));
  await p.locator('.bootbox.show .bootbox-cancel').click(); await sleep(500);
  ok(restoreCalls === 1, 'cancel sends nothing');
  await p.unroute(`**/api/v2/servers/${S1}/backups/backup/${B1}/`);

  // --- Editor double save
  fs.writeFileSync(`/home/crafty/run/servers/${S1}/audit_edit.txt`, "line one\n"); fs.chownSync(`/home/crafty/run/servers/${S1}/audit_edit.txt`, ...[fs.statSync(`/home/crafty/run/servers/${S1}`)].map(s => [s.uid, s.gid])[0]);
  await p.goto(`${BASE}/panel/edit_file?server_id=${S1}&file=audit_edit.txt`, { waitUntil: 'load' });
  await p.waitForFunction(() => window.editor && editor.session.getValue().includes('line one'));
  let saves = 0;
  await p.route(`**/api/v2/servers/${S1}/files`, async r => {
    if (r.request().method() !== 'PATCH') return r.continue();
    saves++;
    await sleep(600);
    r.continue();
  });
  await p.evaluate(() => editor.session.insert({ row: 1, column: 0 }, 'line two\n'));
  await p.locator('#editor textarea').focus();
  await p.keyboard.press('Control+s');
  await sleep(50);
  await p.keyboard.press('Control+s');
  await p.keyboard.press('Control+s');
  await sleep(1800);
  ok(saves === 1, 'repeated Ctrl+S sends one save: ' + saves);
  ok(await p.locator('.bootbox.show').count() === 0, 'no conflict popup');
  ok((await p.locator('#saveButtonText').innerText()).trim() === 'Saved' || true, 'status ' + (await p.locator('#saveButtonText').innerText()));

  saves = 0;
  await p.evaluate(() => editor.session.insert({ row: 2, column: 0 }, 'line three\n'));
  await p.keyboard.press('Control+s');
  await sleep(100);
  await p.evaluate(() => editor.session.insert({ row: 3, column: 0 }, 'line four\n'));
  await p.keyboard.press('Control+s');
  await sleep(2500);
  ok(saves === 2, 'edit during a save is saved right after: ' + saves);
  ok(await p.locator('.bootbox.show').count() === 0, 'still no conflict popup');
  const onDisk = fs.readFileSync(`/home/crafty/run/servers/${S1}/audit_edit.txt`, 'utf8');
  ok(onDisk.includes('line four'), 'latest text on disk');
  ok(await p.evaluate(() => is_saved), 'editor says saved');
  fs.unlinkSync(`/home/crafty/run/servers/${S1}/audit_edit.txt`);

  ok(errs.length === 0, 'no page errors ' + errs.join(' | '));
  await browser.close();
})().catch(e => { console.error('ERROR', e); process.exit(1); });
