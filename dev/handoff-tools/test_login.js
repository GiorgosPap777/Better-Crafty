const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const SP = __dirname;
const BASE = L.BASE;
const mfa = JSON.parse(fs.readFileSync(SP + '/mfa.json'));
const totp = () => L.totp(mfa.secret);
const ok = (c, m) => console.log((c ? 'PASS ' : 'FAIL ') + m);
(async () => {
  const browser = await chromium.launch(L.launchOptions);
  const newPage = async (vp) => {
    const ctx = await browser.newContext({ viewport: vp || { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
    const page = await ctx.newPage();
    page._bad = [];
    page.on('pageerror', e => page._bad.push('pageerror: ' + e.message));
    page.on('response', r => { if (r.status() >= 400 && !/api\/v2\/auth\/login/.test(r.url())) page._bad.push(r.status() + ' ' + r.url()); });
    return page;
  };

  // A: page renders cleanly
  for (const [label, vp] of [['desk', { width: 1440, height: 900 }], ['mob', { width: 390, height: 844 }]]) {
    const p = await newPage(vp);
    await p.goto(BASE + '/login', { waitUntil: 'networkidle' });
    await p.screenshot({ path: `${SP}/shots/after-${label}-login.png` });
    ok(p._bad.length === 0, `${label}: no failed requests / page errors ${p._bad.join(' | ')}`);
    ok(await p.locator('#mfa-step').isHidden(), `${label}: MFA field hidden initially`);
    ok(await p.evaluate(() => document.activeElement.id) === 'username', `${label}: username autofocused`);
    await p.context().close();
  }

  // B + C: MFA flow with next redirect
  let p = await newPage();
  await p.goto(BASE + '/login?next=' + encodeURIComponent('/panel/panel_config'), { waitUntil: 'networkidle' });
  await p.fill('#username', 'Tester');
  await p.fill('#password', 'TesterPass123');
  await p.click('#toggle-password');
  ok(await p.getAttribute('#password', 'type') === 'text', 'password toggle shows password');
  await p.click('#toggle-password');
  await p.press('#password', 'Enter');
  await p.waitForSelector('#mfa-step:not([hidden])', { timeout: 5000 }).catch(() => {});
  ok(await p.locator('#mfa-step').isVisible(), 'MFA step revealed after correct password');
  ok(await p.evaluate(() => document.activeElement.id) === 'totp', 'MFA input focused');
  ok((await p.textContent('#error-field')).trim() === '', 'no error shown for MFA prompt');
  await p.screenshot({ path: `${SP}/shots/after-desk-login-mfa.png` });
  await p.waitForTimeout(31000); // TOTP replay protection: use a fresh code
  const code = totp();
  await p.fill('#totp', code.slice(0, 3) + ' ' + code.slice(3));
  await p.press('#totp', 'Enter');
  await p.waitForURL(u => u.pathname === '/panel/panel_config', { timeout: 8000 }).catch(() => {});
  ok(/\/panel\/panel_config/.test(p.url()), 'TOTP login lands on ?next page: ' + p.url() + ' err=' + await p.textContent('#error-field').catch(()=>'-'));
  // H: already logged in -> /login redirects
  await p.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
  ok(/\/panel\/dashboard/.test(p.url()), 'visiting /login while logged in redirects to dashboard: ' + p.url());
  await p.goto(BASE + '/logout');
  ok(/\/login$/.test(p.url()), 'logout returns to login');
  await p.context().close();

  // F: backup code typed loosely
  p = await newPage({ width: 390, height: 844 });
  await p.goto(BASE + '/login', { waitUntil: 'networkidle' });
  await p.fill('#username', 'tester');
  await p.fill('#password', 'TesterPass123');
  await p.click('#login-submit');
  await p.waitForSelector('#mfa-step:not([hidden])', { timeout: 5000 });
  await p.click('#toggle-mfa-type');
  ok((await p.textContent('#auth-code-label')).includes('Backup'), 'switched to backup code mode');
  await p.screenshot({ path: `${SP}/shots/after-mob-login-backup.png` });
  // Each backup code works once: use the next unused one on every run
  const idxFile = SP + '/backup_idx';
  const idx = fs.existsSync(idxFile) ? parseInt(fs.readFileSync(idxFile, 'utf8'), 10) : 1;
  fs.writeFileSync(idxFile, String(idx + 1));
  await p.fill('#totp', mfa.backup[idx].replace(/-/g, '').toLowerCase());
  await p.click('#login-submit');
  await p.waitForSelector('.bootbox', { timeout: 8000 }).catch(() => {});
  ok(await p.locator('.bootbox').isVisible(), 'burned-backup-code warning shown');
  await p.click('.bootbox .btn-primary');
  await p.waitForURL(u => u.pathname === '/panel/dashboard', { timeout: 8000 }).catch(() => {});
  ok(/dashboard/.test(p.url()), 'backup code login works: ' + p.url());
  await p.context().close();

  // I: logout without session
  p = await newPage();
  const r = await p.goto(BASE + '/logout');
  ok(r.status() < 400 && /\/login$/.test(p.url()), 'logout without a session does not 500');
  const r2 = await p.goto(BASE + '/login?foo=bar');
  ok(r2.status() === 200, '/login?foo=bar renders (' + r2.status() + ')');
  const r3 = await p.goto(BASE + '/login?next=//evil.example');
  ok((await p.getAttribute('#login-form', 'data-next')) === '', 'open redirect next ignored');

  // D + G: wrong password, then cooldown
  await p.goto(BASE + '/login', { waitUntil: 'networkidle' });
  await p.click('#login-submit');
  ok((await p.textContent('#error-field')).length > 0, 'empty submit shows validation message: ' + await p.textContent('#error-field'));
  for (let i = 0; i < 4; i++) {
    await p.fill('#username', 'admin');
    await p.fill('#password', 'wrongpassword' + i);
    await p.click('#login-submit');
    await p.waitForTimeout(900);
  }
  const err = await p.textContent('#error-field');
  ok(/\d\d:\d\d/.test(err), 'cooldown countdown shown: ' + err);
  ok(await p.isDisabled('#login-submit'), 'submit disabled during cooldown');
  await p.screenshot({ path: `${SP}/shots/after-desk-login-cooldown.png` });
  ok(p._bad.filter(b => !/auth\/login/.test(b)).length === 0, 'no unexpected errors: ' + p._bad.join(' | '));
  await browser.close();
})();
