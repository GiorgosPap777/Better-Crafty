const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const TOKEN = L.token();
const tag = process.argv[2] || 'hdr';
(async () => {
  const b = await chromium.launch(L.launchOptions);
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, ignoreHTTPSErrors: true, isMobile: true, hasTouch: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  const p = await ctx.newPage();
  p.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) console.log('ERR', e.message); });
  await p.goto(`${L.BASE}/panel/server_detail?id=${L.S1}&subpage=term`, { waitUntil: 'networkidle' });
  await p.waitForTimeout(1500);
  await p.screenshot({ path: `${__dirname}/shots/${tag}-mob-full.png`, fullPage: true });
  await p.click('.server-details-toggle'); await p.waitForTimeout(300);
  await p.screenshot({ path: `${__dirname}/shots/${tag}-mob-open.png` });
  console.log('term top:', await p.evaluate(() => { const t = document.querySelector('#virt_console, .terminal, #server_log'); return t ? Math.round(t.getBoundingClientRect().top + (document.scrollingElement.scrollTop || 0)) : null; }));
  await b.close();
})();
