const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const SP = __dirname, BASE = 'https://localhost:8443';
const TOKEN = fs.readFileSync(SP + '/token', 'utf8').trim();
const S1 = '669ae1ce-61fa-498d-9782-6f3bb1804313', B1 = 'be668426-9dad-4194-92f2-87d0d4fd6575';
const ok = (c, m) => console.log((c ? 'PASS ' : 'FAIL ') + m);
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: 'localhost', path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) errs.push(e.message); });

  // Backup exclusion picker
  await p.goto(`${BASE}/panel/edit_backup?id=${S1}&backup_id=${B1}`, { waitUntil: 'networkidle' });
  await p.click('#root_files_button');
  await p.waitForSelector('.tree-file', { timeout: 10000 });
  await p.waitForTimeout(800);
  ok(await p.evaluate(() => !window.__xss), 'backup picker: malicious file name does not run script');
  const shown = await p.evaluate(() => [...document.querySelectorAll('.tree-file')].map(e => e.textContent.trim()));
  ok(shown.some(t => t.includes('<img src=x onerror=window.__xss=1>.txt')), 'backup picker: name shown as text');
  const val = await p.evaluate(() => [...document.querySelectorAll('.tree-file input')].map(e => e.value).find(v => v.includes('onerror')));
  ok(val && val.endsWith('<img src=x onerror=window.__xss=1>.txt'), 'backup picker: checkbox value is the real path');

  // File manager
  await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=files`, { waitUntil: 'networkidle' });
  await p.waitForSelector('#files-table-body tr.file');
  const row = p.locator('#files-table-body tr', { hasText: 'onerror' });
  await row.locator('.context-button').click();
  await p.waitForSelector('#context-menu #delete');
  await p.click('#context-menu #delete');
  await p.waitForSelector('.bootbox.modal.show');
  await p.waitForTimeout(400);
  ok(await p.evaluate(() => !window.__xss), 'delete dialog: name does not run script');
  const title = await p.textContent('.bootbox .modal-title');
  ok(title.includes('<img src=x'), 'delete dialog title shows name as text: ' + title.trim().slice(-50));
  const btns = await p.$$eval('.bootbox .modal-footer button', bs => bs.map(b => b.textContent.trim()));
  ok(btns.every(t => t && t !== 'undefined'), 'delete dialog buttons have labels: ' + btns.join(' / '));
  await p.click('.bootbox .modal-footer .btn-link');
  await p.waitForTimeout(500);

  // Open a file whose name has %, # and &
  const [ed] = await Promise.all([ctx.waitForEvent('page'), p.locator('#files-table-body tr', { hasText: '100% #1' }).locator('.column-1').click()]);
  await ed.waitForLoadState('load'); await ed.waitForTimeout(2500);
  const edErr = [];
  ed.on('pageerror', e => edErr.push(e.message));
  const content = await ed.evaluate(() => (window.ace && document.querySelector('.ace_editor')) ? ace.edit(document.querySelector('.ace_editor')).getValue() : document.body.innerText.slice(0, 200));
  ok(content.includes('hello'), 'editor opens file with % # & in name: ' + JSON.stringify(content.slice(0, 40)));
  await ed.close();

  // Load more: rows past 500 are clickable
  await p.locator('#files-table-body tr.directory', { hasText: 'many' }).locator('.column-1').dispatchEvent('mousedown');
  await p.waitForSelector('#get_more', { timeout: 10000 });
  await p.click('#get_more');
  await p.waitForTimeout(500);
  const count = await p.locator('#files-table-body tr.file').count();
  ok(count === 520, 'load more shows all 520 files: ' + count);
  const lastRow = p.locator('#files-table-body tr.file').last();
  await lastRow.locator('.context-button').click();
  ok(await p.isVisible('#context-menu #rename'), 'context menu works on a row added by load more');
  await p.keyboard.press('Escape');

  // Rename inside a folder whose name matches the file
  await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=files&dir=` + encodeURIComponent(`/home/crafty/run/servers/${S1}/world/data`), { waitUntil: 'networkidle' });
  await p.waitForTimeout(1000);
  const wrow = p.locator('#files-table-body tr', { hasText: 'world.txt' });
  if (await wrow.count()) {
    await wrow.locator('.context-button').click();
    await p.click('#context-menu #rename');
    await p.waitForSelector('.bootbox-input');
    await p.fill('.bootbox-input', 'renamed.txt');
    await p.click('.bootbox .btn-primary');
    await p.waitForTimeout(1200);
    const dp = await p.locator('#files-table-body tr', { hasText: 'renamed.txt' }).getAttribute('data-path');
    ok(dp && dp.replace(/^\//, '') === 'world/data/renamed.txt', 'rename updates only the file name in the path: ' + dp);
  } else ok(false, 'could not open world/data');

  // Upload a file with a non-Latin name
  await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=files`, { waitUntil: 'networkidle' });
  await p.click('#upload-file');
  await p.setInputFiles('#files', { name: 'κόσμος.txt', mimeType: 'text/plain', buffer: Buffer.from('γεια') });
  await p.click('.bootbox .modal-footer button');
  await p.waitForTimeout(4000);
  const up = `/home/crafty/run/servers/${S1}/κόσμος.txt`;
  ok(fs.existsSync(up) && fs.readFileSync(up, 'utf8') === 'γεια', 'upload with Greek file name works');

  ok(errs.length === 0, 'no page errors ' + errs.join(' | '));
  await browser.close();
})();
