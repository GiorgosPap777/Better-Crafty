const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const SP = __dirname, BASE = 'https://localhost:8443';
const TOKEN = fs.readFileSync(SP + '/token', 'utf8').trim();
const S1 = '669ae1ce-61fa-498d-9782-6f3bb1804313';
const q = process.argv[2] || '';
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  for (const [tag, vp] of [['desk', { width: 1440, height: 900 }], ['mob', { width: 390, height: 844 }]]) {
    const ctx = await browser.newContext({ viewport: vp, ignoreHTTPSErrors: true, isMobile: tag === 'mob', hasTouch: tag === 'mob' });
    await ctx.addCookies([{ name: 'token', value: TOKEN, domain: 'localhost', path: '/', secure: true }]);
    const p = await ctx.newPage();
    p.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) console.log('ERR', e.message); });
    p.on('console', m => { if (m.type() === 'error' && !/ServiceWorker|favicon/.test(m.text())) console.log('CONSOLE', m.text()); });
    await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=metrics${q}`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(1000);
    await p.evaluate(() => { const el = document.querySelector('.metrics-toolbar'); document.querySelector('.main-panel').scrollTop += el.getBoundingClientRect().top - 80; });
    await p.waitForTimeout(300);
    await p.screenshot({ path: `${SP}/shots/met-${tag}.png` });
    console.log(tag, 'charts:', await p.evaluate(() => charts.length), 'active:', await p.textContent('.metrics-ranges .btn-primary').catch(() => 'none'));
    await ctx.close();
  }
  await browser.close();
})();
