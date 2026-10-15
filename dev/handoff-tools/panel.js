// Usage: node panel.js <outprefix> pages...   (authenticates with token cookie)
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const BASE = 'https://localhost:8443';
const TOKEN = fs.readFileSync(__dirname + '/token', 'utf8').trim();
(async () => {
  const out = process.argv[2];
  const pages = process.argv.slice(3);
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const vps = process.env.ONLY_DESK ? [['desk', { width: 1440, height: 900 }]] : [['desk', { width: 1440, height: 900 }], ['mob', { width: 390, height: 844 }]];
  for (const [label, vp] of vps) {
    const ctx = await browser.newContext({ viewport: vp, ignoreHTTPSErrors: true });
    await ctx.addCookies([{ name: 'token', value: TOKEN, domain: 'localhost', path: '/', secure: true }]);
    const page = await ctx.newPage();
    const logs = [];
    page.on('pageerror', e => logs.push('pageerror: ' + e.message));
    page.on('response', r => { if (r.status() >= 400 && !/announcements|service-worker/.test(r.url())) logs.push(`${r.status()} ${r.url()}`); });
    for (const p of pages) {
      logs.push('--- ' + p);
      await page.goto(BASE + p, { waitUntil: 'networkidle' }).catch(e => logs.push('goto ' + p + ' ' + e.message));
      await page.waitForTimeout(1500);
      const name = p.replace(/id=([0-9a-f]{4})[0-9a-f-]*&?/, '$1_').replace(/[^a-z0-9]+/gi, '_');
      await page.screenshot({ path: `${out}-${label}${name}.png`, fullPage: !process.env.NOFULL });
    }
    console.log(label, [...new Set(logs)].join('\n'));
    await ctx.close();
  }
  await browser.close();
})();
