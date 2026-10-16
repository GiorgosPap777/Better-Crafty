const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const SP = __dirname, BASE = L.BASE;
const TOKEN = L.token();
const S1 = L.S1;
const q = process.argv[2] || '';
(async () => {
  const browser = await chromium.launch(L.launchOptions);
  for (const [tag, vp] of [['desk', { width: 1440, height: 900 }], ['mob', { width: 390, height: 844 }]]) {
    const ctx = await browser.newContext({ viewport: vp, ignoreHTTPSErrors: true, isMobile: tag === 'mob', hasTouch: tag === 'mob' });
    await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
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
