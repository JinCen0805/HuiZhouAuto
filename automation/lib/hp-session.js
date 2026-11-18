// Shared helper: HTTP login to local HP platform + Playwright browser context.
const crypto = require('crypto');
const { chromium } = require('playwright-core');

const BASE = process.env.HP_BASE || 'http://127.0.0.1';
const CHROME = process.env.HP_CHROME || 'C:\\Users\\Grayson\\AppData\\Local\\ms-playwright\\chromium-1234\\chrome-win64\\chrome.exe';

function makeHttp() {
  const jar = new Map();
  const setCookies = (res) => {
    const raw = res.headers.getSetCookie ? res.headers.getSetCookie() : [];
    for (const line of raw) {
      const [pair] = line.split(';');
      const idx = pair.indexOf('=');
      if (idx < 0) continue;
      const name = pair.slice(0, idx).trim();
      const value = pair.slice(idx + 1).trim();
      if (value === '') jar.delete(name); else jar.set(name, value);
    }
  };
  const req = async (p, opts = {}) => {
    const headers = Object.assign({
      Accept: 'application/json, text/javascript, */*; q=0.01',
      'X-Requested-With': 'XMLHttpRequest',
      Cookie: [...jar.entries()].map(([k, v]) => `${k}=${v}`).join('; ')
    }, opts.headers || {});
    let body = opts.body;
    if (body && typeof body === 'object') {
      body = new URLSearchParams(body).toString();
      headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8';
    }
    const res = await fetch(p.startsWith('http') ? p : BASE + p, {
      method: opts.method || (body ? 'POST' : 'GET'), headers, body, redirect: 'manual'
    });
    setCookies(res);
    const text = await res.text();
    let json = null; try { json = JSON.parse(text); } catch (e) {}
    return { status: res.status, text, json, headers: res.headers };
  };
  return { jar, req };
}

function md5(s) { return crypto.createHash('md5').update(s, 'utf8').digest('hex'); }

/**
 * Login via HTTP API (captcha bypass code qwe!@# is present in server code),
 * select platform/role via API, and return cookies + landing URL.
 */
async function loginHttp(user, pass, platformLabel = '采购交易系统') {
  const http = makeHttp();
  await http.req('/Register/login/verification.do');
  const login = await http.req('/Register/login/userLogin.do', {
    body: { username: user, password: md5(pass), checkCode: 'qwe!@#', SimplePwd: '0' }
  });
  if (!login.json || !login.json.success) throw new Error(`login failed for ${user}: ${login.text}`);
  const sel = await http.req('/Register/SelectPlatformAction/select.do', {});
  const data = sel.json && sel.json.data;
  if (!data) throw new Error(`select.do failed for ${user}: ${sel.text}`);
  const platforms = (data.platform || []).flatMap(o => Object.entries(o));
  const plat = platforms.find(([k, v]) => v === platformLabel) || platforms.find(([k, v]) => v.indexOf(platformLabel) >= 0);
  if (!plat) throw new Error(`platform ${platformLabel} not found for ${user}: ${JSON.stringify(platforms)}`);
  const roles = [];
  for (const obj of data.roleCode || []) {
    const entries = Object.entries(obj);
    const p = entries.find(([k]) => k === plat[0]);
    if (p) { const r = entries.find(([k]) => k !== plat[0]); if (r) roles.push({ code: r[0], label: r[1] }); }
  }
  if (!roles.length) throw new Error(`no role for platform ${platformLabel} / ${user}`);
  const role = roles[0];
  const goto = await http.req('/Register/SelectPlatformAction/gotoIndex.do', {
    body: { platform: plat[0], roleCode: role.code, macAddress: '', ipAddress: '' }
  });
  if (!goto.json || !goto.json.data) throw new Error(`gotoIndex failed: ${goto.text}`);
  return {
    user, platform: plat[1], role: role.label, roles,
    target: goto.json.data,
    cookies: [...http.jar.entries()].map(([name, value]) => ({ name, value, domain: '127.0.0.1', path: '/' })),
    http
  };
}

async function openSession(user, pass, opts = {}) {
  const session = await loginHttp(user, pass, opts.platformLabel);
  const browser = await chromium.launch({ executablePath: opts.chrome || CHROME, headless: opts.headless !== false });
  const context = await browser.newContext({ viewport: { width: 1600, height: 900 }, locale: 'zh-CN' });
  await context.addCookies(session.cookies);
  const page = await context.newPage();
  await page.goto(BASE + session.target, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  session.browser = browser;
  session.context = context;
  session.page = page;
  return session;
}

/** Open an HP module inside the index iframe via the app's own changeView(). */
async function openModule(page, title, url, nodeId) {
  await page.evaluate(([t, u, id]) => {
    if (typeof changeView === 'function') return changeView(t, u, id);
    throw new Error('changeView missing');
  }, [title, url, nodeId || '']);
  await page.waitForTimeout(3500);
  const frames = page.frames().filter(f => f.url().indexOf(url) >= 0 || f.name() === title);
  return frames[frames.length - 1];
}

/** 从环境变量读取账号密码，禁止在代码中硬编码。
 *  约定：HP_PASSWORD_<USERNAME 大写，- 换 _>；兼容通用 HP_PASS。
 *  本项目使用 .env.local（gitignore）或运行前注入环境变量。 */
function getPassword(user) {
  const key = 'HP_PASSWORD_' + String(user).toUpperCase().replace(/-/g, '_');
  const pwd = process.env[key] || process.env.HP_PASS;
  if (!pwd) throw new Error(`密码未配置：${key}（或 HP_PASS）。请设置环境变量或 .env.local`);
  return pwd;
}

module.exports = { BASE, CHROME, loginHttp, openSession, openModule, makeHttp, md5, getPassword };
