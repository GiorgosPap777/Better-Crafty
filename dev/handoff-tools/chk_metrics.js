const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const TOKEN = fs.readFileSync(__dirname + '/token', 'utf8').trim();
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: 'localhost', path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) errs.push(e.message); });
  await p.goto('https://localhost:8443/panel/server_detail?id=669ae1ce-61fa-498d-9782-6f3bb1804313&subpage=metrics', { waitUntil: 'networkidle' });
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
