const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const TOKEN = fs.readFileSync(__dirname + '/token', 'utf8').trim();
const tag = process.argv[2] || 'hdr';
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, ignoreHTTPSErrors: true, isMobile: true, hasTouch: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: 'localhost', path: '/', secure: true }]);
  const p = await ctx.newPage();
  p.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) console.log('ERR', e.message); });
  await p.goto('https://localhost:8443/panel/server_detail?id=669ae1ce-61fa-498d-9782-6f3bb1804313&subpage=term', { waitUntil: 'networkidle' });
  await p.waitForTimeout(1500);
  await p.screenshot({ path: `${__dirname}/shots/${tag}-mob-full.png`, fullPage: true });
  await p.click('.server-details-toggle'); await p.waitForTimeout(300);
  await p.screenshot({ path: `${__dirname}/shots/${tag}-mob-open.png` });
  console.log('term top:', await p.evaluate(() => { const t = document.querySelector('#virt_console, .terminal, #server_log'); return t ? Math.round(t.getBoundingClientRect().top + (document.scrollingElement.scrollTop || 0)) : null; }));
  await b.close();
})();
