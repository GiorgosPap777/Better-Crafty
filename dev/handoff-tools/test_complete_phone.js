// Phone layout of the command suggestions, plus a live version from the stats feed
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const SP = __dirname, BASE = 'https://localhost:8443';
const TOKEN = fs.readFileSync(SP + '/token', 'utf8').trim();
const S1 = '669ae1ce-61fa-498d-9782-6f3bb1804313';
const ok = (c, m) => console.log((c ? 'PASS ' : 'FAIL ') + m);
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: 'localhost', path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=term`, { waitUntil: 'networkidle' });
  const input = p.locator('#server_command');
  await input.scrollIntoViewIfNeeded();
  await input.tap();
  await input.type('give ');
  await p.waitForTimeout(200);
  const box = await p.locator('.cmd-suggest').boundingBox();
  const sw = await p.evaluate(() => document.documentElement.scrollWidth);
  ok(box && box.x >= 0 && box.x + box.width <= 390 && sw <= 390, `fits a phone (${JSON.stringify(box)}, page ${sw})`);
  const clipped = await p.$$eval('.cmd-option-text', els => els.filter(e => e.scrollWidth > e.clientWidth + 1).map(e => e.textContent));
  ok(!clipped.length, 'names are not cut off: ' + clipped);
  await p.screenshot({ path: SP + '/complete_phone.png' });

  // The server's start-up line in the log sets the version
  ok(/1\.21\.1 /.test(await p.textContent('#console-hint')), 'version read from the log: ' + await p.textContent('#console-hint'));
  // ... and wins over the status ping
  await p.evaluate(id => window.onServerDetails({ id, running: true, version: 'Paper 1.20.1', players: '["Kai"]' }), S1);
  await p.waitForTimeout(500);
  ok(/1\.21\.1 /.test(await p.textContent('#console-hint')), 'ping does not override the log');
  // A restart that logs a new version switches the data
  await p.evaluate(() => new_line_handler({ line: '<span>[10:00:00] [Server thread/INFO]: Starting minecraft server version 1.21.10<br /></span>' }));
  await p.waitForTimeout(800);
  const hint = await p.textContent('#console-hint');
  ok(/1\.21\.10/.test(hint), 'hint follows the new start-up line: ' + hint);
  // A player saying it in chat does not
  await p.evaluate(() => new_line_handler({ line: '[10:00:01] [Server thread/INFO]: &lt;Kai&gt; Starting minecraft server version 1.16.5<br />' }));
  await p.waitForTimeout(500);
  ok(/1\.21\.10/.test(await p.textContent('#console-hint')), 'chat cannot change it');
  await input.fill('gamerule keep');
  const rules = await p.$$eval('.cmd-option-text', els => els.map(e => e.textContent));
  ok(rules.includes('keepInventory'), '1.21.10 game rule names: ' + rules);
  await input.fill('give ');
  const first = await p.$eval('.cmd-option', e => e.textContent);
  ok(/^Kai/.test(first) && /online/.test(first), 'online player first: ' + first);
  const real = errs.filter(e => !/ServiceWorker|SSL certificate/.test(e));
  ok(!real.length, 'no page errors ' + JSON.stringify(real));
  await browser.close();
})();
