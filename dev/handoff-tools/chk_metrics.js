const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const TOKEN = L.token();
(async () => {
  const b = await chromium.launch(L.launchOptions);
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) errs.push(e.message); });
  await p.goto(`${L.BASE}/panel/server_detail?id=${L.S1}&subpage=metrics`, { waitUntil: 'networkidle' });
  const r = await p.evaluate(() => {
    const c = charts[0]; const { min, max } = c.scales.x; const mid = (min + max) / 2;
    c.zoomScale('x', { min: mid, max }, 'none'); syncTimeAxis(c);
    const synced = charts.every(ch => Math.abs(ch.scales.x.min - mid) < 1000);
    const resetShown = !document.getElementById('reset-button').classList.contains('d-none');
    document.getElementById('reset-button').click();
    const reset = charts.every(ch => Math.abs(ch.scales.x.min - min) < 60000);
    return { synced, resetShown, reset };
  });
  console.log(JSON.stringify(r));
  await p.click('.metrics-ranges a:has-text("6h")');
  await p.waitForLoadState('networkidle');
  console.log('after click:', p.url().includes('hours=6'), await p.textContent('.metrics-ranges .btn-primary'));
  console.log('errors:', errs);
  await b.close();
})();
