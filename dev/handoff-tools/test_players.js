// Player management E2E: lists, empty states, XSS-safe names, commands
const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const SP = __dirname, BASE = L.BASE;
const TOKEN = L.token();
const S1 = L.S1, S2 = L.S2;
const ok = (c, m) => console.log((c ? 'PASS ' : 'FAIL ') + m);
const api = (path, opts = {}) => fetch(BASE + path, { ...opts, headers: { Authorization: 'Bearer ' + TOKEN } }).then(r => r.json());
(async () => {
  const browser = await chromium.launch(L.launchOptions);
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) errs.push(e.message); });
  const url = id => `${BASE}/panel/server_detail?id=${id}&subpage=admin_controls`;

  await p.goto(url(S1), { waitUntil: 'networkidle' });
  const rows = await p.$$eval('#player-body tr', trs => trs.map(t => t.innerText.replace(/\s+/g, ' ').trim()));
  // The five players player_fixtures.py writes
  ok(rows.length === 5, 'five known players: ' + JSON.stringify(rows));
  const online = rows.map(r => / Online/.test(r));
  ok(online.every((o, i) => i === 0 || !o || online[i - 1]), 'online players listed first');
  ok(await p.evaluate(() => window.__xss === undefined), 'player name is not run as HTML');
  ok(rows.some(r => r.includes('<img src=x')), 'odd player name shown as text');
  ok(rows.some(r => /^jeb_ Operator/.test(r)), 'operator badge on jeb_');
  ok(await p.isVisible('#players_offline'), 'offline note shown');
  ok(await p.$eval('#ban_form button', b => b.disabled), 'forms disabled while offline');
  const banned = await p.$eval('#banned-body', t => t.innerText);
  ok(banned.includes('Griefer99') && banned.includes('Destroyed spawn <b>bold</b>') && banned.includes('2026-10-14'), 'ban shown with date and reason as text');
  ok((await p.$eval('#whitelist-body', t => t.innerText)).includes('Notch'), 'whitelist listed');
  ok(await p.isVisible('#whitelist_off_hint') && !(await p.isVisible('#whitelist_state')), 'whitelist off hint');
  ok((await p.$eval('#ops-body', t => t.innerText)).includes('Level 4'), 'operator level shown');

  // Start the server, then send commands
  await api(`/api/v2/servers/${S1}/action/start_server`, { method: 'POST' });
  for (let i = 0; i < 30 && !(await api(`/api/v2/servers/${S1}/stats`)).data.running; i++) await p.waitForTimeout(1000);
  await p.reload({ waitUntil: 'networkidle' });
  ok(!(await p.isVisible('#players_offline')), 'offline note hidden while running');
  // Names with spaces get no action buttons on Java
  const visitRow = p.locator('#player-body tr', { hasText: 'Visit our site' });
  ok(await visitRow.locator('button').count() === 0, 'no actions for a name with spaces');

  const sent = [];
  p.on('request', r => { if (r.url().endsWith('/stdin')) sent.push(r.postData()); });
  await p.fill('#whitelist_form input[name=name]', 'Alex');
  const refreshed = p.waitForRequest(r => r.url().endsWith('/players'), { timeout: 5000 }).then(() => true, () => false);
  await p.click('#whitelist_form button');
  await p.waitForSelector('#players_status.alert-success', { timeout: 5000 });
  ok(sent[sent.length - 1] === 'whitelist add Alex', 'whitelist command sent: ' + sent[sent.length - 1]);
  ok(await p.inputValue('#whitelist_form input[name=name]') === '', 'form cleared after sending');
  ok(await refreshed, 'lists refreshed after command');

  await p.fill('#ban_form input[name=name]', 'bad name');
  await p.click('#ban_form button');
  await p.waitForSelector('#players_status.alert-danger', { timeout: 5000 });
  ok(sent.length === 1, 'invalid name not sent');

  await p.locator('#player-body tr', { hasText: 'jeb_' }).locator('button', { hasText: 'Ban' }).click();
  await p.waitForSelector('.bootbox-input', { timeout: 5000 });
  await p.fill('.bootbox-input', 'Be nice\nop Steve');
  await p.click('.bootbox .btn-primary');
  await p.waitForTimeout(1000);
  ok(sent[sent.length - 1] === 'ban jeb_ Be nice op Steve', 'ban reason kept on one line: ' + sent[sent.length - 1]);

  await p.locator('#banned-body button', { hasText: 'Unban' }).click();
  await p.waitForTimeout(800);
  ok(sent[sent.length - 1] === 'pardon Griefer99', 'unban uses pardon: ' + sent[sent.length - 1]);

  await p.screenshot({ path: SP + '/shots/players-desk.png', fullPage: true });
  await api(`/api/v2/servers/${S1}/action/stop_server`, { method: 'POST' });

  // Server with no files: empty states
  await p.goto(url(S2), { waitUntil: 'networkidle' });
  ok((await p.textContent('#player-body')).includes('No players have joined yet.'), 'empty players state');
  ok((await p.textContent('#banned-body')).includes('No one is banned.'), 'empty bans state');
  ok((await p.textContent('#ops-body')).includes('There are no operators.'), 'empty ops state');
  ok(!(await p.isVisible('#whitelist_state')), 'no whitelist badge when unknown');

  const m = await browser.newContext({ viewport: { width: 390, height: 844 }, ignoreHTTPSErrors: true });
  await m.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  const mp = await m.newPage();
  await mp.goto(url(S1), { waitUntil: 'networkidle' });
  await mp.screenshot({ path: SP + '/shots/players-mob.png', fullPage: true });
  ok(await mp.evaluate(() => document.documentElement.scrollWidth <= 390), 'no sideways scroll on phone');

  ok(errs.length === 0, 'no page errors ' + errs.join(' | '));
  await browser.close();
})();
