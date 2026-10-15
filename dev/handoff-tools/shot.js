// Usage: node shot.js <outprefix> [pages...]  pages are paths after login, e.g. /panel/dashboard
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const BASE = 'https://localhost:8443';
const creds = JSON.parse(fs.readFileSync('/home/crafty/run/app/config/default-creds.txt', 'utf8'));
const PASS = process.env.CRAFTY_PASS || creds.password;
(async () => {
  const out = process.argv[2];
  const pages = process.argv.slice(3);
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  for (const [label, vp] of [['desk', { width: 1440, height: 900 }], ['mob', { width: 390, height: 844 }]]) {
    const ctx = await browser.newContext({ viewport: vp, ignoreHTTPSErrors: true });
    const page = await ctx.newPage();
    const logs = [];
    page.on('console', m => { if (m.type() === 'error') logs.push('console: ' + m.text()); });
    page.on('pageerror', e => logs.push('pageerror: ' + e.message));
    page.on('response', r => { if (r.status() >= 400) logs.push(`${r.status()} ${r.url()}`); });
    await page.goto(BASE + '/login', { waitUntil: 'networkidle' });
    await page.screenshot({ path: `${out}-${label}-login.png`, fullPage: true });
    await page.fill('#username', 'admin');
    await page.fill('#password', 'wrongpassword');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${out}-${label}-login-error.png`, fullPage: true });
    if (pages.length) {
      await page.fill('#password', PASS);
      await page.keyboard.press('Enter');
      await page.waitForURL(/panel/, { timeout: 10000 }).catch(() => logs.push('login did not redirect'));
      for (const p of pages) {
        await page.goto(BASE + p, { waitUntil: 'networkidle' }).catch(e => logs.push('goto ' + p + ' ' + e.message));
        await page.waitForTimeout(1500);
        const name = p.replace(/[^a-z0-9]+/gi, '_');
        await page.screenshot({ path: `${out}-${label}${name}.png`, fullPage: true });
      }
    }
    console.log(label, logs.join('\n'));
    await ctx.close();
  }
  await browser.close();
})();
