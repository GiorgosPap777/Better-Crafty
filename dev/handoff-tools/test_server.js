const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const SP = __dirname, BASE = L.BASE;
const TOKEN = L.token();
const S2 = L.S2;
const ok = (c, m) => console.log((c ? 'PASS ' : 'FAIL ') + m);
(async () => {
  const browser = await chromium.launch(L.launchOptions);
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) errors.push(e.message); });
  p.on('dialog', d => d.accept());
  await p.goto(`${BASE}/panel/server_detail?id=${S2}&subpage=term`, { waitUntil: 'networkidle' });
  await p.evaluate(() => { window.__noReload = true; });
  const state = () => p.textContent('#server-state');
  const btn = a => p.locator(`.server-action[data-action="${a}"]`);
  // Crafty pops a "no internet" warning on start in this sandbox; dismiss it
  const dismiss = async () => {
    await p.waitForTimeout(1500);
    await p.evaluate(() => document.querySelectorAll('.bootbox, .modal-backdrop').forEach(e => e.remove()));
    await p.evaluate(() => document.body.classList.remove('modal-open'));
  };
  ok((await state()).includes('Offline'), 'starts offline: ' + (await state()).trim());
  ok(await btn('start_server').isEnabled() && await btn('stop_server').isDisabled(), 'only Start enabled when offline');
  ok(await p.evaluate(() => document.activeElement.id) === 'server_command', 'command input focused');
  ok(await p.evaluate(() => window.scrollY) === 0, 'page not scrolled by focus');

  // Command while offline
  await p.fill('#server_command', 'list');
  await p.press('#server_command', 'Enter');
  await p.waitForSelector('.bootbox', { timeout: 5000 }).catch(() => {});
  ok((await p.textContent('.bootbox').catch(() => '')).includes('not running'), 'offline command shows friendly message');
  await p.click('.bootbox .btn-primary').catch(() => {});
  await p.waitForTimeout(500);

  // Start
  await btn('start_server').click();
  await p.waitForTimeout(300);
  ok((await state()).includes('Starting'), 'shows Starting... while pending: ' + (await state()).trim());
  await p.waitForFunction(() => document.querySelector('#server-state').textContent.includes('Online'), null, { timeout: 30000 }).catch(() => {});
  ok((await state()).includes('Online'), 'becomes Online without reload: ' + (await state()).trim());
  ok(await p.evaluate(() => window.__noReload === true), 'no full page reload happened');
  ok(await btn('start_server').isDisabled() && await btn('stop_server').isEnabled(), 'Stop/Restart enabled once online');
  await dismiss();
  await p.focus('#server_command');
  await p.waitForFunction(() => document.querySelector('#virt_console').textContent.includes('Done ('), null, { timeout: 15000 }).catch(() => {});
  ok((await p.textContent('#virt_console')).includes('Done ('), 'console shows server output');
  await p.screenshot({ path: SP + '/shots/after-desk-server-running.png' });

  // Commands + history
  await p.press('#server_command', 'Enter'); // empty -> ignored
  for (const c of ['say hello world', 'list']) {
    await p.fill('#server_command', c);
    await p.press('#server_command', 'Enter');
    await p.waitForTimeout(400);
  }
  await p.waitForFunction(() => document.querySelector('#virt_console').textContent.includes('[Server] hello world'), null, { timeout: 8000 }).catch(() => {});
  ok((await p.textContent('#virt_console')).includes('[Server] hello world'), 'command output appears in console');
  ok(await p.inputValue('#server_command') === '', 'input cleared after send');
  await p.fill('#server_command', 'draft');
  await p.press('#server_command', 'ArrowUp'); const h1 = await p.inputValue('#server_command');
  await p.press('#server_command', 'ArrowUp'); const h2 = await p.inputValue('#server_command');
  await p.press('#server_command', 'ArrowUp'); const h3 = await p.inputValue('#server_command');
  await p.press('#server_command', 'ArrowDown'); const h4 = await p.inputValue('#server_command');
  await p.press('#server_command', 'ArrowDown'); const h5 = await p.inputValue('#server_command');
  // History holds the earlier (offline) "list" too: [list, say hello world, list]
  ok(h1 === 'list' && h2 === 'say hello world' && h3 === 'list' && h4 === 'say hello world' && h5 === 'list',
    `history navigation: ${[h1, h2, h3, h4, h5].join(' | ')}`);
  await p.fill('#server_command', '');

  // Restart
  const startedBefore = await p.textContent('#started');
  await p.waitForTimeout(1500);
  await btn('restart_server').click();
  await p.waitForTimeout(300);
  ok((await state()).includes('Restarting'), 'shows Restarting...');
  await p.waitForFunction((b) => document.querySelector('#server-state').textContent.includes('Online') && document.querySelector('#started').textContent !== b, startedBefore, { timeout: 60000 }).catch(() => {});
  ok((await state()).includes('Online') && (await p.textContent('#started')) !== startedBefore, 'restart completes with new start time');
  await dismiss();

  // Stop
  await btn('stop_server').click();
  await p.waitForTimeout(300);
  ok((await state()).includes('Stopping'), 'shows Stopping...');
  await p.waitForFunction(() => document.querySelector('#server-state').textContent.includes('Offline'), null, { timeout: 60000 }).catch(() => {});
  ok((await state()).includes('Offline'), 'stop completes: ' + (await state()).trim());

  // Kill via menu (needs confirmation)
  await btn('start_server').click();
  await p.waitForFunction(() => document.querySelector('#server-state').textContent.includes('Online'), null, { timeout: 30000 }).catch(() => {});
  await dismiss();
  await p.click('.server-more');
  await p.screenshot({ path: SP + '/shots/after-desk-server-menu.png' });
  await btn('kill_server').click();
  await p.waitForSelector('.bootbox', { timeout: 5000 });
  await p.screenshot({ path: SP + '/shots/after-desk-server-kill-confirm.png' });
  await p.click('.bootbox .btn-danger');
  await p.waitForFunction(() => document.querySelector('#server-state').textContent.includes('Offline'), null, { timeout: 60000 }).catch(() => {});
  ok((await state()).includes('Offline'), 'kill completes: ' + (await state()).trim());
  ok(await p.evaluate(() => window.__noReload === true), 'still no full page reload');

  // Header on another tab
  await p.goto(`${BASE}/panel/server_detail?id=${S2}&subpage=config`, { waitUntil: 'networkidle' });
  ok(await btn('start_server').isVisible(), 'controls available on Config tab');
  ok(errors.length === 0, 'no page errors: ' + errors.join(' | '));
  await browser.close();
})();
