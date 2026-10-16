const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const TOKEN = L.token();
const S1 = L.S1;
const BASE = L.BASE;
const OUT = __dirname + '/shots/';
(async () => {
  const b = await chromium.launch(L.launchOptions);
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errors = [];
  p.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  p.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
  // The named cards; test_item_icons.js covers the item pictures
  await p.route('**/api/v2/crafty/item_icons/', route => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ status: 'ok', data: { state: 'none' } }),
  }));

  for (const [uuid, want] of [['069a79f4-44e9-4726-a5be-fca90e38aaf5', 200], ['00000000-0000-4000-8000-000000000000', 404], ['abc-123', 400]]) {
    const r = await p.request.get(`${BASE}/api/v2/servers/${S1}/players/${uuid}`, { headers: { Authorization: 'Bearer ' + TOKEN } });
    console.log('API', uuid, r.status(), r.status() === want ? 'OK' : 'UNEXPECTED');
  }
  const r = await p.request.get(`${BASE}/api/v2/servers/${S1}/players`, { headers: { Authorization: 'Bearer ' + TOKEN } });
  console.log('overview known:', (await r.json()).data.known.length);

  await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=admin_controls`, { waitUntil: 'load' });
  await p.waitForSelector('#player-body tr');
  console.log('rows:', await p.$$eval('#player-body tr', rows => rows.map(r => r.innerText.replace(/\s+/g, ' ').trim())));
  await p.locator('#player-body').screenshot({ path: OUT + 'list.png' });
  await p.screenshot({ path: OUT + 'page.png', fullPage: true });

  await p.locator('#player-body tr', { hasText: 'Notch' }).getByRole('button', { name: 'Details' }).click();
  await p.waitForSelector('#player_modal_body:not([hidden])');
  await p.waitForTimeout(400);
  await p.screenshot({ path: OUT + 'overview.png' });
  for (const [tab, name] of [['#player_tab_inventory', 'inventory'], ['#player_tab_ender', 'ender'], ['#player_tab_stats', 'stats'], ['#player_tab_advancements', 'advancements']]) {
    await p.click(`a[href="${tab}"]`);
    await p.waitForTimeout(350);
    if (name === 'inventory') await p.locator('#player_tab_inventory button.inv-slot').first().click();
    await p.screenshot({ path: OUT + name + '.png' });
  }
  console.log('item info:', await p.locator('#player_tab_inventory .item-info').innerText());
  await p.click('a[href="#player_tab_stats"]'); await p.waitForTimeout(300);
  await p.fill('.player-stats-search', 'zombie');
  console.log('stats rows (zombie):', await p.$$eval('#player_tab_stats tbody tr', rows => rows.map(r => r.innerText.replace(/\s+/g, ' '))));
  await p.click('#player_modal .close'); await p.waitForSelector('#player_modal', { state: 'hidden' });
  await p.waitForTimeout(500);

  // Old-format player and a player with no stats
  for (const name of ['jeb_', 'Alex_Builder']) {
    await p.locator('#player-body tr', { hasText: name }).getByRole('button', { name: 'Details' }).click();
    await p.waitForSelector('#player_modal_body:not([hidden])');
    await p.waitForTimeout(400);
    console.log(name, 'overview:', (await p.locator('#player_tab_overview .player-cards').innerText()).replace(/\s+/g, ' '));
    await p.click('a[href="#player_tab_inventory"]');
    await p.waitForTimeout(300);
    console.log(name, 'items:', await p.$$eval('#player_tab_inventory button.inv-slot', els => els.map(e => e.getAttribute('aria-label'))));
    if (name === 'jeb_') await p.screenshot({ path: OUT + 'jeb_inventory.png' });
    await p.click('a[href="#player_tab_stats"]');
    await p.waitForTimeout(300);
    console.log(name, 'stats:', (await p.locator('#player_tab_stats').innerText()).slice(0, 120).replace(/\s+/g, ' '));
    await p.click('#player_modal .close'); await p.waitForSelector('#player_modal', { state: 'hidden' });
    await p.waitForTimeout(500);
  }
  // Unknown-name player
  await p.locator('#player-body tr', { hasText: 'f0e1d2c3' }).getByRole('button', { name: 'Details' }).click();
  await p.waitForSelector('#player_modal_body:not([hidden])');
  console.log('noname title:', await p.locator('#player_modal_title').innerText(), '|', await p.locator('#player_tab_overview').innerText().then(t => t.slice(-90).replace(/\s+/g, ' ')));
  await p.click('#player_modal .close'); await p.waitForSelector('#player_modal', { state: 'hidden' });
  await p.waitForTimeout(500);
  // XSS player name
  await p.locator('#player-body tr', { hasText: 'onerror' }).getByRole('button', { name: 'Details' }).click();
  await p.waitForSelector('#player_modal_body:not([hidden])');
  await p.waitForTimeout(300);
  console.log('xss flags:', await p.evaluate(() => [window.__xss, window.__xss2, document.querySelectorAll('img[src="x"]').length]));
  await p.click('#player_modal .close'); await p.waitForSelector('#player_modal', { state: 'hidden' });

  // Search
  await p.waitForTimeout(500);
  console.log('search visible:', await p.isVisible('#player_search'));

  // Phone
  await p.setViewportSize({ width: 390, height: 844 });
  await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=admin_controls`, { waitUntil: 'load' });
  await p.waitForSelector('#player-body tr');
  await p.locator('#player-body').screenshot({ path: OUT + 'phone_list.png' });
  await p.locator('#player-body tr', { hasText: 'Notch' }).getByRole('button', { name: 'Details' }).click();
  await p.waitForSelector('#player_modal_body:not([hidden])');
  await p.waitForTimeout(400);
  await p.screenshot({ path: OUT + 'phone_overview.png' });
  await p.click('a[href="#player_tab_inventory"]');
  await p.waitForTimeout(400);
  await p.screenshot({ path: OUT + 'phone_inventory.png' });
  console.log('phone horizontal overflow:', await p.evaluate(() => document.querySelector('#player_modal .modal-body').scrollWidth - document.querySelector('#player_modal .modal-body').clientWidth));
  console.log('console errors:', errors);
  await b.close();
})();
