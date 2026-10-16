// README screenshots. Usage: node readme_shots.js <before|after> <outdir> [name...]
const L = require('./local');
const { chromium } = L;
const fs = require('fs');
const BASE = L.BASE;
const TOKEN = L.token();
const S1 = L.S1;
const B1 = L.B1;
const [which, outDir, ...only] = process.argv.slice(2);
const DESK = { width: 1280, height: 800 }, PHONE = { width: 390, height: 844 };
const server = sub => `/panel/server_detail?id=${S1}&subpage=${sub}`;

// Scroll so the server tab bar sits just under the top navbar
const toTabs = async p => p.evaluate(() => {
  const tabs = document.querySelector('.tab-simple-styled');
  if (!tabs) return;
  // The Files page scrolls an inner panel instead of the window
  const panel = document.querySelector('.main-panel');
  if (panel && panel.scrollHeight > panel.clientHeight + 1 && getComputedStyle(panel).overflowY === 'auto') {
    panel.scrollTop += tabs.getBoundingClientRect().top - 80;
  } else {
    window.scrollTo(0, tabs.getBoundingClientRect().top + window.scrollY - 80);
  }
});

// Open a player's details window on the given tab
const openPlayer = (tab, slot) => async p => {
  await p.locator('#player-body tr', { hasText: 'Notch' }).getByRole('button', { name: 'Details' }).click();
  await p.waitForSelector('#player_modal_body:not([hidden])');
  await p.click(`a[href="${tab}"]`);
  await p.waitForTimeout(500);
  if (slot) await p.locator(`${tab} button.inv-slot`, { hasText: slot }).first().click();
};

const SHOTS = [
  { name: 'login', url: '/login', vp: DESK, auth: false },
  { name: 'login-phone', url: '/login', vp: PHONE, auth: false },
  { name: 'dashboard', url: '/panel/dashboard', vp: DESK },
  { name: 'terminal', url: server('term'), vp: DESK, prep: p => p.evaluate(() => window.scrollTo(0, 0)) },
  { name: 'terminal-phone', url: server('term'), vp: PHONE, prep: p => p.evaluate(() => window.scrollTo(0, 0)) },
  { name: 'terminal-complete', url: server('term'), vp: DESK, afterOnly: true,
    prep: async p => {
      await p.evaluate(() => { const f = document.querySelector('#command-form'); window.scrollTo(0, f.getBoundingClientRect().bottom + window.scrollY - 720); });
      await p.click('#server_command');
      await p.keyboard.type('give ');
    } },
  { name: 'config', url: server('config'), vp: DESK, prep: toTabs },
  { name: 'config-game', url: server('config'), vp: DESK, afterOnly: true,
    prep: p => p.evaluate(() => { const s = document.querySelector('#game-settings'); window.scrollTo(0, s.getBoundingClientRect().top + window.scrollY - 80); }) },
  { name: 'players', url: server('admin_controls'), vp: DESK, prep: toTabs },
  { name: 'player-inventory', url: server('admin_controls'), vp: DESK, afterOnly: true,
    prep: openPlayer('#player_tab_inventory', 'Netherite Sword') },
  { name: 'player-stats', url: server('admin_controls'), vp: DESK, afterOnly: true, prep: openPlayer('#player_tab_stats') },
  { name: 'backups', url: server('backup'), vp: DESK, prep: toTabs },
  { name: 'backup-files', url: `/panel/edit_backup?id=${S1}&backup_id=${B1}`, vp: DESK,
    prep: p => p.evaluate(() => { const t = document.querySelector('.restore_button'); if (t) window.scrollTo(0, t.closest('table, .card').getBoundingClientRect().top + window.scrollY - 120); }) },
  { name: 'files', url: server('files'), vp: DESK, prep: toTabs },
  { name: 'files-phone', url: server('files'), vp: PHONE, prep: toTabs },
  { name: 'metrics', url: server('metrics'), vp: DESK, prep: toTabs },
  { name: 'logs', url: server('logs'), vp: DESK, prep: toTabs },
  { name: 'schedules', url: server('schedules'), vp: DESK, prep: toTabs },
];

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch(L.launchOptions);
  for (const shot of SHOTS) {
    if (only.length && !only.includes(shot.name)) continue;
    if (shot.afterOnly && which !== 'after') continue;
    const ctx = await browser.newContext({ viewport: shot.vp, deviceScaleFactor: 1, ignoreHTTPSErrors: true, isMobile: shot.vp === PHONE, hasTouch: shot.vp === PHONE });
    if (shot.auth !== false) await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
    const p = await ctx.newPage();
    await p.goto(BASE + shot.url, { waitUntil: 'load' });
    await p.waitForTimeout(3500);
    // Sandbox-only "no internet" popups and toasts are not part of the UI being shown
    await p.evaluate(() => {
      document.querySelectorAll('.bootbox, .modal-backdrop, .popover, .toast').forEach(e => e.remove());
      document.body.classList.remove('modal-open');
    });
    if (shot.prep) await shot.prep(p);
    await p.waitForTimeout(600);
    await p.screenshot({ path: `${outDir}/${shot.name}-${which}.png` });
    console.log('shot', shot.name);
    await ctx.close();
  }
  await browser.close();
})().catch(e => { console.error('ERROR', e); process.exit(1); });
