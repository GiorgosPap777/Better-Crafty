// Backups tab E2E: summaries, back up now, delete plan
const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const SP = __dirname, BASE = L.BASE;
const TOKEN = L.token();
const S1 = L.S1, S2 = L.S2;
const B1 = L.B1;
const ok = (c, m) => console.log((c ? 'PASS ' : 'FAIL ') + m);
const api = (path, opts = {}) => fetch(BASE + path, { ...opts, headers: { Authorization: 'Bearer ' + TOKEN } }).then(r => r.json());
(async () => {
  const before = fs.readdirSync(`${L.RUN}/backups/${S1}/${B1}`).length;
  const created = await api(`/api/v2/servers/${S1}/backups/`, { method: 'POST', body: JSON.stringify({ backup_name: 'Temp <b>plan</b>', max_backups: 3 }) });
  ok(created.status === 'ok', 'temp plan created ' + JSON.stringify(created).slice(0, 120));

  const browser = await chromium.launch(L.launchOptions);
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) errs.push(e.message); });
  const url = id => `${BASE}/panel/server_detail?id=${id}&subpage=backup`;

  await p.goto(url(S1), { waitUntil: 'networkidle' });
  const plans = p.locator('.backup-plan');
  ok(await plans.count() === 2, 'two plans listed');
  const def = plans.filter({ hasText: 'Default Backup' });
  const facts = (await def.locator('.backup-facts').innerText()).replace(/\s+/g, ' ');
  ok(facts.includes(`${before} / Unlimited`), 'kept count shown: ' + facts);
  ok(/\d{4}-\d{2}-\d{2} \d{2}:\d{2} .*ago/.test(facts), 'last backup time shown');
  ok((await def.locator('.backup-status').innerText()).trim() === 'Standby', 'status badge text');
  const temp = plans.filter({ hasText: 'Temp <b>plan</b>' });
  ok(await temp.count() === 1, 'plan name shown as text');
  ok((await temp.locator('.backup-facts').innerText()).includes('None yet'), 'no backups yet for new plan');
  ok((await temp.locator('.backup-facts').innerText()).includes('0 / 3'), 'max backups shown');
  ok(await def.locator('.del_button').count() === 0, 'default plan cannot be deleted');

  // Back up now
  const reloaded = p.waitForEvent('framenavigated', { timeout: 60000 });
  await def.locator('.backup_now_button').click();
  ok(await p.locator('.backup_now_button').first().isDisabled(), 'buttons disabled while backing up');
  // Backup ids are UUIDs and may start with a digit, which a #id selector does not allow
  ok(await p.waitForSelector(`[id="${B1}_status"] :text("Completed")`, { timeout: 30000 }).then(() => true, () => false), 'completed shown');
  await reloaded;
  await p.waitForLoadState('networkidle');
  const after = fs.readdirSync(`${L.RUN}/backups/${S1}/${B1}`).length;
  ok(after === before + 1, `backup file made (${before} -> ${after})`);
  const facts2 = (await p.locator('.backup-plan', { hasText: 'Default Backup' }).locator('.backup-facts').innerText()).replace(/\s+/g, ' ');
  ok(facts2.includes(`${after} / Unlimited`), 'page reloaded with new count: ' + facts2);

  // Delete the temp plan
  await p.locator('.backup-plan', { hasText: 'Temp <b>plan</b>' }).locator('.del_button').click();
  await p.waitForSelector('.bootbox-confirm', { timeout: 5000 });
  const msg = await p.locator('.bootbox-confirm .bootbox-body').innerText();
  ok(msg.includes('not deleted'), 'delete dialog explains files stay: ' + msg);
  await p.click('.bootbox-confirm .btn-danger');
  await p.waitForLoadState('networkidle');
  await p.waitForTimeout(1500);
  ok(await p.locator('.backup-plan').count() === 1, 'temp plan deleted');
  await p.screenshot({ path: SP + '/shots/backups-desk.png', fullPage: true });

  const m = await browser.newContext({ viewport: { width: 390, height: 844 }, ignoreHTTPSErrors: true });
  await m.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  const mp = await m.newPage();
  await mp.goto(url(S1), { waitUntil: 'networkidle' });
  await mp.screenshot({ path: SP + '/shots/backups-mob.png', fullPage: true });
  ok(await mp.evaluate(() => document.documentElement.scrollWidth <= 390), 'no sideways scroll on phone');

  ok(errs.length === 0, 'no page errors ' + errs.join(' | '));
  await browser.close();
})();
