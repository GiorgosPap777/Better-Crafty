const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const SP = __dirname, BASE = L.BASE;
const TOKEN = L.token();
const S1 = L.S1;
(async () => {
  const browser = await chromium.launch(L.launchOptions);
  for (const [tag, vp] of [['desk', { width: 1440, height: 900 }], ['mob', { width: 390, height: 844 }]]) {
    const ctx = await browser.newContext({ viewport: vp, ignoreHTTPSErrors: true, isMobile: tag === 'mob', hasTouch: tag === 'mob' });
    await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
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
