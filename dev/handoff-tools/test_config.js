// Config tab E2E: game settings (server.properties) + memory fields
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const SP = __dirname, BASE = 'https://localhost:8443';
const TOKEN = fs.readFileSync(SP + '/token', 'utf8').trim();
const S1 = '669ae1ce-61fa-498d-9782-6f3bb1804313', S2 = '15673394-a460-4bc9-aee6-61150b6853c3';
const PROPS = `/home/crafty/run/servers/${S1}/server.properties`;
const ok = (c, m) => console.log((c ? 'PASS ' : 'FAIL ') + m);
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: 'localhost', path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) errs.push(e.message); });
  p.on('dialog', d => d.accept());

  await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=config`, { waitUntil: 'networkidle' });
  await p.waitForSelector('#prop_difficulty', { timeout: 10000 });
  ok(await p.isVisible('#game-settings'), 'game settings section shown');
  ok(await p.inputValue('#prop_motd') === '§aA Minecraft Server', 'motd decoded: ' + await p.inputValue('#prop_motd'));
  ok(await p.inputValue('#mem_min') === '0.25' && await p.inputValue('#mem_max') === '0.5', 'memory shown in GB');

  await p.selectOption('#prop_difficulty', 'hard');
  await p.fill('#prop_max-players', '42');
  await p.fill('#prop_motd', '§bΓεια σου');
  await p.click('label[for="prop_pvp"]');
  await p.click('#properties_save');
  await p.waitForSelector('#properties_status.alert-success', { timeout: 5000 });
  const text = fs.readFileSync(PROPS, 'utf8');
  ok(/^difficulty=hard$/m.test(text) && /^max-players=42$/m.test(text) && /^pvp=false$/m.test(text), 'file updated');
  ok(/^motd=\\u00a7b\\u0393\\u03b5\\u03b9\\u03b1 \\u03c3\\u03bf\\u03c5$/m.test(text), 'motd written with escapes');
  ok(/^level-name=world$/m.test(text) && text.startsWith('#Minecraft server properties'), 'other lines kept');

  // Memory: change max to 1 GB and min to 0.5 GB
  await p.fill('#mem_min', '2');
  await p.fill('#mem_max', '1');
  await p.click('#config_save');
  await p.waitForTimeout(500);
  ok(await p.evaluate(() => !document.getElementById('mem_max').validity.valid), 'min above max is blocked');
  await p.fill('#mem_min', '0.5');
  await p.fill('#mem_max', '1');
  ok(await p.isVisible('#config_dirty'), 'unsaved changes notice shown');
  await Promise.all([p.waitForNavigation({ waitUntil: 'networkidle' }), p.click('#config_save')]);
  const cmd = await p.inputValue('#execution_command');
  ok(cmd === 'java -Xms512M -Xmx1024M -jar server.jar nogui', 'start command updated: ' + cmd);
  ok(await p.inputValue('#mem_max') === '1', 'memory field shows new value');

  // Server whose server.properties has no known settings: section stays hidden
  await p.goto(`${BASE}/panel/server_detail?id=${S2}&subpage=config`, { waitUntil: 'networkidle' });
  await p.waitForTimeout(800);
  ok(!(await p.isVisible('#game-settings')), 'section hidden when there is nothing to edit');
  ok(await p.isVisible('.config-danger'), 'danger zone shown');
  ok(errs.length === 0, 'no page errors ' + errs.join(' | '));
  await browser.close();
})();
