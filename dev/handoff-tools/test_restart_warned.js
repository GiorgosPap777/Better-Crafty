// Restart with in-game warnings: the panel menu item, countdown, Cancel, the
// API, a full one-minute countdown, and the schedule form. Takes about 2 minutes.
const L = require('./local');
const { chromium } = L;
const TOKEN = L.token();
const S1 = L.S1;
const BASE = L.BASE;

(async () => {
  const b = await chromium.launch(L.launchOptions);
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await ctx.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  const p = await ctx.newPage();
  const errors = [];
  // The service worker fails on the self-signed certificate and the news
  // feed needs the internet; neither is about this page
  p.on('pageerror', e => { if (!/ServiceWorker/.test(e.message)) errors.push('PAGEERROR ' + e.message); });
  p.on('console', m => { if (m.type() === 'error' && !/SSL|ServiceWorker|Failed to load resource/.test(m.text())) errors.push('CONSOLE ' + m.text()); });
  p.on('response', r => { if (r.status() >= 400 && !/announcements|service-worker|favicon/.test(r.url())) errors.push(`${r.status()} ${r.url().replace(BASE, '')}`); });
  const auth = { headers: { Authorization: 'Bearer ' + TOKEN } };
  const api = async (method, url, data) => {
    const res = await p.request.fetch(`${BASE}/api/v2/servers/${S1}${url}`, { method, ...auth, data });
    return { code: res.status(), body: await res.json() };
  };
  const stats = async () => (await api('GET', '/stats')).body.data;
  const consoleText = async () => (await api('GET', '/logs')).body.data.join('\n');
  const check = (ok, what) => console.log(`${ok ? 'PASS' : 'FAIL'} ${what}`);

  // A running server
  if (!(await stats()).running) {
    await api('POST', '/action/start_server');
    for (let i = 0; i < 30 && !(await stats()).running; i++) await p.waitForTimeout(1000);
  }
  await api('POST', '/action/cancel_restart');
  check((await stats()).running, 'server is running');

  // API checks
  let r = await api('POST', '/action/restart_server/7');
  check(r.code === 400 && r.body.error === 'INVALID_WARNING_TIME', 'a warning time that is not offered is refused');
  r = await api('POST', '/action/cancel_restart');
  check(r.code === 409 && r.body.error === 'NO_RESTART_PENDING', 'cancel with nothing to cancel says so');

  // Menu item and dialog
  await p.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=term`, { waitUntil: 'load' });
  check(await p.isHidden('#restart-countdown'), 'no countdown banner at first');
  await p.click('.server-more');
  await p.click('[data-action="restart_warned"]');
  await p.waitForSelector('#restart-warn-minutes');
  check(await p.inputValue('#restart-warn-minutes') === '5', 'dialog offers 5 minutes first');
  const options = await p.locator('#restart-warn-minutes option').allInnerTexts();
  check(options.join('|') === '1 minute|2 minutes|5 minutes|10 minutes|15 minutes|30 minutes', 'dialog choices: ' + options.join(', '));
  await p.waitForTimeout(400);
  await p.screenshot({ path: 'shots/restart_warned_dialog.png' });
  await p.selectOption('#restart-warn-minutes', '2');
  await p.click('.bootbox .btn-primary');
  await p.waitForSelector('#restart-countdown:not(.d-none)', { timeout: 10000 });
  const text = await p.innerText('#restart-countdown-text');
  check(/^Restarting in (2:00|1:5\d)$/.test(text), 'countdown banner shows ' + text);
  check(await p.isEnabled('.server-action[data-action="restart_server"]'), 'Restart button stays usable');
  await p.waitForTimeout(1500);
  check(/\[Server\] Restarting in 2 minutes\./.test(await consoleText()), 'players are told in the game chat');
  const left = (await stats()).restart_in;
  check(left > 100 && left <= 120, 'stats API reports the seconds left: ' + left);
  await p.screenshot({ path: 'shots/restart_warned_banner.png' });

  // The countdown survives a reload
  await p.reload({ waitUntil: 'load' });
  check(await p.isVisible('#restart-countdown'), 'banner is back after a reload');

  // Cancel
  await p.click('#restart-cancel');
  await p.waitForSelector('#restart-countdown.d-none', { state: 'attached', timeout: 5000 });
  check(true, 'Cancel hides the banner');
  await p.waitForTimeout(1500);
  check(/\[Server\] Restart cancelled\./.test(await consoleText()), 'players are told the restart is off');
  check((await stats()).restart_in === null, 'no countdown after Cancel');

  // Stop ends a countdown
  r = await api('POST', '/action/restart_server/1');
  check(r.body.data && r.body.data.restart_in === 60, 'API starts a 1 minute countdown');
  await api('POST', '/action/stop_server');
  for (let i = 0; i < 30 && (await stats()).running; i++) await p.waitForTimeout(1000);
  check((await stats()).restart_in === null, 'stopping the server ends the countdown');
  await api('POST', '/action/start_server');
  for (let i = 0; i < 30 && !(await stats()).running; i++) await p.waitForTimeout(1000);

  // A full countdown restarts the server
  await p.reload({ waitUntil: 'load' });
  const startedBefore = (await stats()).started;
  r = await api('POST', '/action/restart_server/1');
  await p.waitForSelector('#restart-countdown:not(.d-none)', { timeout: 10000 });
  check(true, 'banner appears for a countdown started elsewhere');
  await p.waitForTimeout(61000);
  check(await p.isHidden('#restart-countdown'), 'banner is gone at zero');
  let restarted = false;
  for (let i = 0; i < 40 && !restarted; i++) {
    await p.waitForTimeout(1000);
    const s = await stats();
    restarted = s.running && s.started !== startedBefore;
  }
  check(restarted, 'server restarted at the end of the countdown');

  // Schedules (and leftovers from an earlier run that stopped half way)
  for (const old of (await api('GET', '/tasks/')).body.data.filter(t => t.name === 'Nightly warned')) {
    await api('DELETE', `/tasks/${old.schedule_id}`);
  }
  r = await api('POST', '/tasks/', { name: 'Bad warn', action: 'restart', action_id: '7', interval: 1, interval_type: 'days', command: 'restart_server' });
  check(r.body.error === 'INVALID_WARNING_TIME', 'schedule with a warning time that is not offered is refused');
  await p.goto(`${BASE}/panel/add_schedule?id=${S1}`, { waitUntil: 'load' });
  check(await p.isHidden('#ifRestart'), 'warning choice hidden for Start');
  await p.selectOption('#action', 'restart');
  check(await p.isVisible('#restart_warning'), 'warning choice shown for Restart');
  await p.fill('#name_input', 'Nightly warned');
  await p.selectOption('#restart_warning', '10');
  await p.fill('#time', '04:00');
  await p.click('#new_schedule_form button[type="submit"]');
  await p.waitForURL(/subpage=schedules/, { timeout: 10000 });
  const tasks = (await api('GET', '/tasks/')).body.data;
  const task = tasks.find(t => t.name === 'Nightly warned');
  check(task && task.action === 'restart' && task.action_id === '10' && task.command === 'restart_server', 'schedule saved with 10 minutes: ' + JSON.stringify(task && { action: task.action, action_id: task.action_id }));
  if (task) {
    await p.goto(`${BASE}/panel/edit_schedule?id=${S1}&sch_id=${task.schedule_id}`, { waitUntil: 'load' });
    check(await p.inputValue('#restart_warning') === '10', 'edit page shows the saved warning time');
    await p.screenshot({ path: 'shots/restart_warned_schedule.png', fullPage: true });
    await p.selectOption('#restart_warning', '');
    await p.click('#schedule_form button[type="submit"]');
    await p.waitForURL(/subpage=schedules/, { timeout: 10000 });
    // This endpoint returns the schedule itself, without a "data" wrapper
    const again = (await api('GET', `/tasks/${task.schedule_id}`)).body;
    check(again.action_id === '', 'warning removed: ' + JSON.stringify(again.action_id));
    await api('DELETE', `/tasks/${task.schedule_id}`);
  }

  // Phone width
  await api('POST', '/action/restart_server/30');
  const phone = await b.newContext({ viewport: { width: 375, height: 800 }, ignoreHTTPSErrors: true, isMobile: true });
  await phone.addCookies([{ name: 'token', value: TOKEN, domain: L.HOST, path: '/', secure: true }]);
  const pp = await phone.newPage();
  await pp.goto(`${BASE}/panel/server_detail?id=${S1}&subpage=term`, { waitUntil: 'load' });
  await pp.waitForSelector('#restart-countdown:not(.d-none)');
  const overflow = await pp.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  check(!overflow, 'no sideways scrolling at phone width');
  await pp.screenshot({ path: 'shots/restart_warned_phone.png' });
  await api('POST', '/action/cancel_restart');

  check(errors.length === 0, 'no page errors' + (errors.length ? ': ' + errors.join(' | ') : ''));
  await b.close();
})();
