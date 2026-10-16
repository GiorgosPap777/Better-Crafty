// Item pictures in the player details window: the game-style inventory with
// the player's skin and the health, food and experience under it, tooltip,
// shulker contents, the ender chest, phone width, and the offer to make the
// pictures (faked with page.route so nothing is downloaded).
//
// Needs pictures in <Crafty>/app/config/item_icons: a super user presses
// "Show item pictures" once, or see "Item pictures" in handoff.md.
const L = require('./local');
const { chromium } = L;
const TOKEN = L.token();
const S1 = L.S1;
const BASE = L.BASE;
const OUT = __dirname + '/shots/';
const ok = (c, m) => console.log((c ? 'PASS ' : 'FAIL ') + m);
const PAGE = `${BASE}/panel/server_detail?id=${S1}&subpage=admin_controls`;

async function openPlayer(p, name, tab) {
  await p.goto(PAGE, { waitUntil: 'load' });
  await p.waitForSelector('#player-body tr');
  await p.locator('#player-body tr', { hasText: name }).getByRole('button', { name: 'Details' }).click();
  await p.waitForSelector('#player_modal_body:not([hidden])');
  await p.click(`a[href="${tab}"]`);
  await p.waitForTimeout(500);
}

// Pictures that did not load show the item's name instead
async function pictures(p, pane) {
  return p.$$eval(`${pane} .mc-slot`, slots => ({
    slots: slots.length,
    pictures: slots.filter(s => { const i = s.querySelector('img.mc-icon'); return i && i.complete && i.naturalWidth > 0; }).length,
    names: slots.filter(s => s.querySelector('.mc-slot-text')).map(s => s.textContent),
  }));
}

(async () => {
  const b = await chromium.launch(L.launchOptions);
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errors = [];
  p.on('console', m => { if (m.type() === 'error' && !/404/.test(m.text())) errors.push(m.text()); });
  p.on('pageerror', e => errors.push('PAGEERROR ' + e.message));

  const auth = { headers: { Authorization: 'Bearer ' + TOKEN } };
  const status = await (await p.request.get(`${BASE}/api/v2/crafty/item_icons/`, auth)).json();
  ok(status.data.state === 'ready' && status.data.count > 1000, 'pictures are there: ' + JSON.stringify(status.data));
  const sword = await p.request.get(`${BASE}/api/v2/crafty/item_icons/diamond_sword.png`, auth);
  ok(sword.status() === 200 && sword.headers()['content-type'] === 'image/png', 'a picture is served');
  ok((await p.request.get(`${BASE}/api/v2/crafty/item_icons/no_such_item.png`, auth)).status() === 404, 'missing picture is 404');
  ok((await p.request.get(`${BASE}/api/v2/crafty/item_icons/Bad.png`, auth)).status() === 404, 'odd names do not match the route');

  // Skins: Notch has a Mojang UUID (his own skin with internet, else the
  // default the game gives him); only players of this server are looked up
  const skinUrl = uuid => `${BASE}/api/v2/servers/${S1}/players/${uuid}/skin`;
  const skin = await p.request.get(skinUrl('069a79f4-44e9-4726-a5be-fca90e38aaf5'), auth);
  ok(skin.status() === 200 && skin.headers()['content-type'] === 'image/png' && /^(wide|slim)$/.test(skin.headers()['x-skin-model']),
    'skin served: ' + skin.headers()['x-skin-model']);
  ok((await p.request.get(skinUrl('00000000-0000-4000-8000-000000000000'), auth)).status() === 404, 'no skin for strangers');
  // Node's fetch has no login cookie, unlike p.request
  ok((await fetch(skinUrl('069a79f4-44e9-4726-a5be-fca90e38aaf5'))).status === 403, 'skin needs a login');

  // Inventory
  await openPlayer(p, 'Notch', '#player_tab_inventory');
  await p.waitForTimeout(500);
  const inv = await pictures(p, '#player_tab_inventory');
  // 41 of the player's and 5 of the crafting grid
  ok(inv.slots === 46, `46 slots (${inv.slots})`);
  console.log('pictures:', inv.pictures, 'names instead:', inv.names);
  ok(await p.$$eval('#player_tab_inventory .mc-hud-icon', e => e.length) === 20, 'ten hearts and ten food');
  ok(await p.isVisible('#player_tab_inventory .mc-xp-level'), 'experience level shown');
  const hud = await p.evaluate(() => {
    const box = s => document.querySelector('#player_tab_inventory ' + s).getBoundingClientRect();
    const panel = box('.mc-panel'), xp = box('.mc-xp'), hearts = box('.mc-hearts'), food = box('.mc-food');
    return {
      below: xp.top >= panel.bottom && hearts.top >= xp.bottom && food.top >= xp.bottom,
      sides: Math.abs(hearts.left - panel.left) < 1 && Math.abs(food.right - panel.right) < 1,
    };
  });
  ok(hud.below && hud.sides, 'level and bar under the inventory, then hearts left and food right ' + JSON.stringify(hud));
  // The skin is drawn and turns to follow the pointer
  await p.waitForSelector('#player_tab_inventory .mc-player.mc-has-skin canvas');
  const drawn = () => p.$eval('#player_tab_inventory .mc-player canvas', c => {
    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    let filled = 0, sum = 0;
    for (let i = 0; i < d.length; i += 4) if (d[i + 3]) { filled++; sum += (i / 4) % c.width; }
    return { filled: filled / (d.length / 4), middle: sum / filled / c.width };
  });
  const box = await p.locator('#player_tab_inventory .mc-player').boundingBox();
  await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await p.waitForTimeout(150);
  const ahead = await drawn();
  ok(ahead.filled > 0.15 && ahead.filled < 0.6, 'player drawn: ' + JSON.stringify(ahead));
  await p.mouse.move(box.x + box.width / 2 + 400, box.y + box.height / 2);
  await p.waitForTimeout(150);
  const turned = await drawn();
  ok(JSON.stringify(turned) !== JSON.stringify(ahead), 'player turns to the pointer: ' + JSON.stringify(turned));
  ok(await p.$$eval('#player_tab_inventory .mc-slot.mc-selected', e => e.length) === 1, 'selected hotbar slot marked');
  ok(await p.$$eval('#player_tab_inventory .mc-glint', e => e.length) >= 1, 'enchanted items shine');
  await p.locator('#player_tab_inventory .mc-wrap').screenshot({ path: OUT + 'icons_inventory.png' });

  // Tooltip on hover
  const enchanted = p.locator('#player_tab_inventory button.mc-slot:has(.mc-glint)').first();
  await enchanted.hover();
  await p.waitForTimeout(200);
  const tip = await p.locator('.mc-tooltip').innerText();
  ok(await p.isVisible('.mc-tooltip') && /minecraft:/.test(tip), 'tooltip: ' + tip.replace(/\n/g, ' | '));
  await p.locator('#player_modal .modal-content').screenshot({ path: OUT + 'icons_tooltip.png' });
  await p.mouse.move(5, 5);
  await p.waitForTimeout(100);
  ok(!(await p.isVisible('.mc-tooltip')), 'tooltip hides when the pointer leaves');

  // Shulker box contents
  const shulker = p.locator('#player_tab_inventory button.mc-slot[aria-label*="Shulker"]').first();
  await shulker.click();
  await p.waitForTimeout(300);
  const contents = await p.$$eval('#player_tab_inventory .item-info .mc-contents .mc-slot', s => s.map(e => e.getAttribute('aria-label')));
  ok(contents.length === 27 && contents[0] && contents[1], 'shulker contents placed by slot: ' + contents.filter(Boolean));
  ok(await p.isVisible('#player_tab_inventory .item-info .item-info-icon'), 'details show the picture');
  await p.locator('#player_tab_inventory .mc-wrap').screenshot({ path: OUT + 'icons_shulker.png' });

  // Ender chest
  await p.click('a[href="#player_tab_ender"]');
  await p.waitForTimeout(400);
  const ender = await pictures(p, '#player_tab_ender');
  ok(ender.slots === 27, `ender chest 27 slots (${ender.slots})`);
  await p.locator('#player_tab_ender .mc-wrap').screenshot({ path: OUT + 'icons_ender.png' });

  // Stats top lists
  await p.click('a[href="#player_tab_stats"]');
  await p.waitForTimeout(400);
  ok(await p.$$eval('.player-top-icon', e => e.length) > 0, 'top lists have pictures');
  await p.locator('.player-top-lists').screenshot({ path: OUT + 'icons_stats.png' });

  // Old-format player (1.12 ids and NBT)
  await openPlayer(p, 'jeb_', '#player_tab_inventory');
  const jeb = await pictures(p, '#player_tab_inventory');
  console.log('jeb_ pictures:', jeb.pictures, 'names instead:', jeb.names);

  // Phone
  await p.setViewportSize({ width: 390, height: 844 });
  await openPlayer(p, 'Notch', '#player_tab_inventory');
  const body = await p.evaluate(() => {
    const m = document.querySelector('#player_modal .modal-body');
    const panel = document.querySelector('#player_tab_inventory .mc-panel').getBoundingClientRect();
    return { overflow: m.scrollWidth - m.clientWidth, panel: [panel.left, panel.right], slot: document.querySelector('#player_tab_inventory .mc-slot').getBoundingClientRect().width };
  });
  ok(body.overflow <= 0 && body.panel[1] <= 390, 'fits a phone: ' + JSON.stringify(body));
  await p.screenshot({ path: OUT + 'icons_phone.png' });
  await p.locator('#player_tab_inventory button.mc-slot').first().tap().catch(() => p.locator('#player_tab_inventory button.mc-slot').first().click());
  await p.waitForTimeout(300);
  await p.screenshot({ path: OUT + 'icons_phone_info.png', fullPage: false });
  await p.setViewportSize({ width: 1440, height: 900 });

  // Without pictures: the offer, the progress, then the pictures
  let fake = { state: 'none' };
  await p.route('**/api/v2/crafty/item_icons/', route => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ status: 'ok', data: fake }),
  }));
  await openPlayer(p, 'Notch', '#player_tab_inventory');
  ok(await p.$$eval('#player_tab_inventory button.inv-slot', e => e.length) > 0, 'named cards without pictures');
  const offer = p.locator('#player_tab_inventory .item-icons-notice');
  ok(/Show item pictures/.test(await offer.innerText()), 'offer shown: ' + (await offer.innerText()).replace(/\n/g, ' | '));
  await p.locator('#player_tab_inventory').screenshot({ path: OUT + 'icons_offer.png' });
  fake = { state: 'working', step: 'download', done: 20e6, total: 40e6, version: '26.3' };
  await offer.getByRole('button').click();
  await p.waitForTimeout(300);
  ok(/50%/.test(await offer.innerText()), 'progress: ' + await offer.innerText());
  fake = { state: 'working', step: 'draw', done: 600, total: 1600, version: '26.3' };
  await p.waitForTimeout(2300);
  ok(/600 \/ 1600/.test(await offer.innerText()), 'drawing: ' + await offer.innerText());
  await p.locator('#player_tab_inventory .item-icons-notice').screenshot({ path: OUT + 'icons_progress.png' });
  fake = status.data;
  await p.waitForTimeout(2300);
  ok(await p.$$eval('#player_tab_inventory .mc-slot', e => e.length) === 46, 'switches to pictures when they are done');
  fake = { ...status.data, state: 'error', error: 'Network is unreachable' };
  await p.click('#player_tab_inventory .item-icons-notice button');
  await p.waitForTimeout(300);
  ok(/Network is unreachable/.test(await p.locator('#player_tab_inventory .item-icons-notice').innerText()), 'error shown with a retry');
  await p.unroute('**/api/v2/crafty/item_icons/');

  // The sandbox has no service worker certificate or Crafty news feed (424)
  const real = errors.filter(e => !/ServiceWorker|SSL certificate|424/.test(e));
  ok(!real.length, 'no page errors ' + JSON.stringify(real));
  await b.close();
})();
