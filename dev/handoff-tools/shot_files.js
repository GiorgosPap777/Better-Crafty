const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const SP = __dirname, BASE = 'https://localhost:8443';
const TOKEN = fs.readFileSync(SP + '/token', 'utf8').trim();
const S1 = '669ae1ce-61fa-498d-9782-6f3bb1804313';
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  for (const [tag, vp] of [['desk', { width: 1440, height: 900 }], ['mob', { width: 390, height: 844 }]]) {
    const ctx = await browser.newContext({ viewport: vp, ignoreHTTPSErrors: true, isMobile: tag === 'mob', hasTouch: tag === 'mob' });
    await ctx.addCookies([{ name: 'token', value: TOKEN, domain: 'localhost', path: '/', secure: true }]);
    const p = await ctx.newPage();
    p.on('pageerror', e => console.log('ERR', e.message));
    await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=files`, { waitUntil: 'networkidle' });
    await p.waitForSelector('#files-table-body tr.file');
    await p.locator('#context-container').scrollIntoViewIfNeeded();
    await p.evaluate(() => document.getElementById('context-container').scrollIntoView());
    await p.screenshot({ path: `${SP}/shots/fm2-${tag}-root.png` });
    await p.locator('#files-table-body tr.directory', { hasText: 'world' }).locator('.column-1').dispatchEvent('mousedown');
    await p.waitForTimeout(1200);
    await p.locator('#files-table-body tr.directory', { hasText: 'data' }).locator('.column-1').dispatchEvent('mousedown');
    await p.waitForTimeout(1200);
    if (tag === 'mob') {
      await p.locator('#files-table-body tr', { hasText: 'world.txt' }).locator('.files-options-btn').click();
      await p.waitForTimeout(400);
    }
    await p.screenshot({ path: `${SP}/shots/fm2-${tag}-sub.png` });
    console.log(tag, await p.textContent('#table-nav'));
    await ctx.close();
  }
  await browser.close();
})();
