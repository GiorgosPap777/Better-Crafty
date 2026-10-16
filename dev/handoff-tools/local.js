// Settings shared by the browser scripts in this folder.
//
// setup_testdata.py writes local.json (URL, Crafty folder, test ids) and the
// token file next to this one; environment variables override them:
// CRAFTY_URL, CRAFTY_DIR, CRAFTY_TOKEN, S1, S2, B1, and CHROME (a Chromium
// to use instead of Playwright's own).
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const saved = (() => {
  try { return JSON.parse(fs.readFileSync(path.join(__dirname, 'local.json'), 'utf8')); } catch (e) { return {}; }
})();

function setting(env, key, fallback) {
  const value = process.env[env] || saved[key] || fallback;
  if (value === undefined) {
    throw new Error(`${key} is not set: run setup_testdata.py first, or set ${env}`);
  }
  return value;
}

function playwright() {
  try {
    return require('playwright');
  } catch (e) {
    // The cloud container had Playwright installed globally here
    const cloud = '/opt/node22/lib/node_modules/playwright';
    if (fs.existsSync(cloud)) return require(cloud);
    throw new Error('Playwright is missing: run "npm install" and "npx playwright install chromium" in ' + __dirname);
  }
}

const CLOUD_CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const chrome = process.env.CHROME || (fs.existsSync(CLOUD_CHROME) ? CLOUD_CHROME : undefined);
const BASE = setting('CRAFTY_URL', 'url', 'https://localhost:8443');

// Crafty uses a self-signed certificate; the scripts that call fetch() need this
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
fs.mkdirSync(path.join(__dirname, 'shots'), { recursive: true });

// Six-digit code for a base32 TOTP secret (what an authenticator app shows)
function totp(secret, now = Date.now()) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  const bits = secret.replace(/=+$/, '').toUpperCase().split('')
    .map(c => alphabet.indexOf(c).toString(2).padStart(5, '0')).join('');
  const key = Buffer.from(bits.match(/.{8}/g).map(b => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(now / 30000)));
  const hash = crypto.createHmac('sha1', key).update(counter).digest();
  const offset = hash[hash.length - 1] & 15;
  return String((hash.readUInt32BE(offset) & 0x7fffffff) % 1e6).padStart(6, '0');
}

module.exports = {
  chromium: playwright().chromium,
  launchOptions: chrome ? { executablePath: chrome } : {},
  BASE,
  HOST: new URL(BASE).hostname,
  totp,
  token: () => process.env.CRAFTY_TOKEN || fs.readFileSync(path.join(__dirname, 'token'), 'utf8').trim(),
  // The folder Crafty runs in (holds servers/, backups/, app/config/)
  get RUN() { return setting('CRAFTY_DIR', 'craftyDir', path.resolve(__dirname, '../..')); },
  get S1() { return setting('S1', 'S1'); },
  get S2() { return setting('S2', 'S2'); },
  get B1() { return setting('B1', 'B1'); },
};
