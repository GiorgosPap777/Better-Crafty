const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const SP = __dirname, BASE = L.BASE;
const TOKEN = L.token();
const S1 = L.S1, B1 = L.B1;
const pages = [
  '/panel/dashboard', '/panel/panel_config', '/panel/config_json', '/panel/custom_login', '/panel/offsite', '/panel/activity_logs',
  '/panel/credits', '/panel/contribute', '/panel/wiki', '/panel/add_user', '/panel/edit_user?id=3', '/panel/edit_user?id=1',
  '/panel/add_role', '/panel/edit_role?id=1', '/panel/edit_user_apikeys?id=1', '/panel/edit_user_otp?id=1', '/panel/edit_user_passkey?id=1',
  `/panel/server_detail?id=${S1}&subpage=logs`, `/panel/server_detail?id=${S1}&subpage=files`, `/panel/server_detail?id=${S1}&subpage=backup`, `/panel/server_detail?id=${S1}&subpage=world`,
  `/panel/server_detail?id=${S1}&subpage=schedules`, `/panel/server_detail?id=${S1}&subpage=config`, `/panel/server_detail?id=${S1}&subpage=admin_controls`,
  `/panel/server_detail?id=${S1}&subpage=metrics`, `/panel/server_detail?id=${S1}&subpage=webhooks`, `/panel/server_detail?id=${S1}&subpage=update_center`,
  `/panel/edit_backup?id=${S1}&backup_id=${B1}`, `/panel/add_backup?id=${S1}`, `/panel/add_schedule?id=${S1}`, `/panel/add_webhook?id=${S1}`,
  `/panel/edit_file?server_id=${S1}&file=` + encodeURIComponent(L.RUN + '/servers/' + S1 + '/server.properties'),
  '/server/step1', '/server/bedrock_step1', '/server/steam_cmd_step1', '/server/hytale_step1', '/status', '/panel/nonexistent', '/does-not-exist',
];
(async () => {
  const browser = await chromium.launch(L.launchOptions);
  const only = process.argv[2];
  for (const [label, vp] of [['desk', { width: 1440, height: 900 }], ['mob', { width: 390, height: 844 }]]) {
    const ctx = await browser.newContext({ viewport: vp, ignoreHTTPSErrors: true });
    await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
    const page = await ctx.newPage();
    let cur = [];
    page.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) cur.push('pageerror: ' + e.message.split('\n')[0]); });
    page.on('response', r => { if (r.status() >= 400 && !/announcements|service-worker|favicon/.test(r.url())) cur.push(`${r.status()} ${r.url().replace(BASE, '')}`); });
    page.on('console', m => { if (m.type() === 'error' && !/SSL|ServiceWorker|Failed to load resource/.test(m.text())) cur.push('console: ' + m.text().slice(0, 160)); });
    for (const p of pages) {
      if (only && !p.includes(only)) continue;
      cur = [];
      let status = '-';
      try {
        const r = await page.goto(BASE + p, { waitUntil: p.includes('edit_file') ? 'load' : 'networkidle', timeout: 20000 });
        status = r ? r.status() : '-';
      } catch (e) { cur.push('goto: ' + e.message.split('\n')[0]); }
      await page.waitForTimeout(800);
      const name = p.replace(/[0-9a-f]{8}-[0-9a-f-]{27}/g, 'X').replace(/[^a-z0-9]+/gi, '_').slice(0, 60);
      await page.screenshot({ path: `${SP}/shots/crawl/${label}${name}.png`, fullPage: true }).catch(() => {});
      const final = page.url().replace(BASE, '');
      console.log(`[${label}] ${status} ${p.slice(0, 70)}${final !== p ? ' -> ' + final.slice(0, 50) : ''}${cur.length ? '\n    ' + [...new Set(cur)].join('\n    ') : ''}`);
    }
    await ctx.close();
  }
  await browser.close();
})();
