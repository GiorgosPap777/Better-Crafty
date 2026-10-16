// Terminal command suggestions E2E (desktop)
const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const SP = __dirname, BASE = L.BASE;
const TOKEN = L.token();
const S1 = L.S1;
const ok = (c, m) => console.log((c ? 'PASS ' : 'FAIL ') + m);
const api = (path, opts = {}) => fetch(BASE + path, { ...opts, headers: { Authorization: 'Bearer ' + TOKEN } }).then(r => r.json());
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  for (let i = 0; i < 30; i++) { try { await api(`/api/v2/servers/${S1}/stats`); break; } catch (e) { await sleep(1000); } }
  await api(`/api/v2/servers/${S1}/action/start_server`, { method: 'POST' });
  let stats;
  for (let i = 0; i < 40 && !(stats = (await api(`/api/v2/servers/${S1}/stats`)).data).running; i++) await sleep(1000);
  for (let i = 0; i < 15 && stats.version === 'False'; i++) { await sleep(1000); stats = (await api(`/api/v2/servers/${S1}/stats`)).data; }
  console.log('server', stats.running, stats.version, stats.players);
  const browser = await chromium.launch(L.launchOptions);
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  p.on('console', m => { if (m.type() === 'error' && !/ServiceWorker|favicon|404/.test(m.text())) errs.push(m.text()); });
  await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=term`, { waitUntil: 'networkidle' });
  const input = p.locator('#server_command');
  const options = () => p.$$eval('.cmd-option', els => els.map(e => e.querySelector('.cmd-option-text').textContent));
  const active = () => p.$eval('.cmd-option.active .cmd-option-text', e => e.textContent).catch(() => null);
  const shown = () => p.isVisible('.cmd-suggest');
  const usage = () => p.$eval('.cmd-suggest-usage', e => e.hidden ? '' : e.textContent);

  const hint = await p.textContent('#console-hint');
  ok(/Tab/.test(hint) && /1\.21\.1 /.test(hint), 'hint names Tab and the version: ' + hint);

  await input.click();
  await input.type('gi');
  ok(await shown(), 'popup opens while typing');
  ok((await options())[0] === 'give', 'give offered: ' + (await options()));
  await p.keyboard.press('Tab');
  ok(await input.inputValue() === 'give ', 'Tab completes the command and adds a space');
  const players = await options();
  // Names come before selectors, saved players A to Z (unless someone is online)
  const names = players.slice(0, players.findIndex(t => t.startsWith('@')));
  const sorted = [...names].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));
  ok((names.length >= 3 && names.join() === sorted.join()) || /Online|online/.test(await p.$eval('.cmd-option-detail', e => e.textContent)), 'player names first, online then A to Z: ' + players.slice(0, 8));
  ok(players.includes('Alex_Builder') && players.includes('@a') && !players.includes('@e'), 'saved players and player selectors');
  ok((await p.$$eval('.cmd-option-detail', e => e.map(x => x.textContent))).includes('All players'), '@a has its description');
  await p.keyboard.press('ArrowDown');
  const second = await active();
  ok(second === players[1], 'Down moves the highlight: ' + second);
  await p.keyboard.press('ArrowUp');
  await p.keyboard.press('ArrowUp');
  ok(await active() === players[players.length - 1], 'Up wraps to the end');
  await p.keyboard.press('Shift+Tab');
  ok(await active() === players[players.length - 2], 'Shift+Tab moves back');
  await input.fill('give Steve dia');
  ok((await options())[0] === 'diamond', 'items: ' + (await options()).slice(0, 5));
  await p.keyboard.press('Enter');
  await p.waitForTimeout(500);
  ok(await input.inputValue() === '' && !(await p.isVisible('.bootbox')), 'Enter without choosing sends what was typed');
  await input.fill('give Steve dia');
  await p.keyboard.press('ArrowDown');
  const picked = await active();
  await p.keyboard.press('Enter');
  ok(await input.inputValue() === `give Steve ${picked} `, 'Enter after choosing completes: ' + await input.inputValue());
  ok(await usage() === '[<count>]' || await usage() === '<count>', 'count hint: ' + await usage());
  await p.screenshot({ path: SP + '/shots/complete_count.png' });

  await input.fill('pardon ');
  ok((await options()).join() === 'Griefer99', 'pardon offers banned players: ' + await options());
  await input.fill('deop ');
  ok((await options()).join() === 'jeb_', 'deop offers operators: ' + await options());
  await input.fill('op ');
  ok(!(await options()).includes('jeb_'), 'op skips operators');
  await input.fill('gamerule keep');
  ok((await options()).includes('keepInventory'), 'game rules: ' + await options());
  await input.fill('tp ');
  ok((await options()).includes('~ ~ ~'), 'coordinates');
  await input.fill('kick Steve ');
  ok(!(await options()).length && /reason/.test(await usage()), 'usage hint for free text: ' + await usage());
  await input.fill('xyz ');
  ok(!(await shown()), 'nothing for unknown commands');

  await input.fill('effect give @a spe');
  ok(await shown(), 'popup open before Escape');
  await p.keyboard.press('Escape');
  ok(!(await shown()), 'Escape hides the popup');
  await p.keyboard.press('Tab');
  ok(await shown() && await input.inputValue() === 'effect give @a spe', 'Tab brings it back');
  await p.keyboard.press('Tab');
  ok(await input.inputValue() === 'effect give @a speed ', 'then completes: ' + await input.inputValue());

  // Popup lines up with the word being completed
  await input.fill('execute as @a run ');
  const boxX = (await p.locator('.cmd-suggest').boundingBox()).x;
  await input.fill('');
  await input.type('e');
  const boxX0 = (await p.locator('.cmd-suggest').boundingBox()).x;
  ok(boxX > boxX0 + 50, `popup follows the word (${boxX0} -> ${boxX})`);

  // Command history still works when the popup is closed
  await input.fill('say hi');
  await p.keyboard.press('Enter');
  await p.waitForTimeout(500);
  ok(await input.inputValue() === '', 'Enter sends the command');
  await p.keyboard.press('ArrowUp');
  ok(await input.inputValue() === 'say hi', 'Up recalls history: ' + await input.inputValue());
  ok(!(await shown()) || !(await options()).length, 'no suggestion list after recalling history');
  await input.fill('');
  await p.keyboard.press('Escape');

  // Screenshot for the README
  await input.fill('');
  await input.type('give @a minecraft:diamond_');
  await p.waitForTimeout(200);
  await p.screenshot({ path: SP + '/shots/complete_desktop.png' });

  // Phone
  await p.setViewportSize({ width: 390, height: 844 });
  await input.fill('');
  await input.type('give ');
  const box = await p.locator('.cmd-suggest').boundingBox();
  const sw = await p.evaluate(() => document.documentElement.scrollWidth);
  ok(box && box.x >= 0 && box.x + box.width <= 390 && sw <= 390, `fits a phone (${JSON.stringify(box)}, page ${sw})`);
  await p.screenshot({ path: SP + '/shots/complete_phone.png' });

  const real = errs.filter(e => !/ServiceWorker|SSL certificate|424/.test(e));
  ok(!real.length, 'no page errors ' + JSON.stringify(real));
  await api(`/api/v2/servers/${S1}/action/stop_server`, { method: 'POST' });
  await browser.close();
})();
