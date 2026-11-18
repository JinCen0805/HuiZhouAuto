// 供应商账号连通性探测：ybjcsgys1~3
// 密码从环境变量读取，不写入仓库：
//   HP_PASSWORD_YBJCSGYS1 / HP_PASSWORD_YBJCSGYS2 / HP_PASSWORD_YBJCSGYS3
// 用法：node explore/probe-supplier-accounts.js
const { loginHttp, BASE } = require('../lib/hp-session');
const fs = require('fs');

function passwordOf(user) {
  const key = 'HP_PASSWORD_' + user.toUpperCase().replace(/-/g, '_');
  const pwd = process.env[key];
  if (!pwd) throw new Error(`环境变量未设置：${key}`);
  return pwd;
}

async function menuOf(session) {
  const res = await fetch(BASE + '/nodeJs/menu_Json?v=probe', {
    headers: {
      Accept: 'application/json, text/javascript, */*; q=0.01',
      'X-Requested-With': 'XMLHttpRequest',
      Cookie: session.cookies.map(c => `${c.name}=${c.value}`).join('; ')
    }
  });
  const json = await res.json();
  const items = Array.isArray(json.content) ? json.content : [];
  const byId = {}; items.forEach(i => (byId[i.id] = i));
  const pathOf = i => { const a = []; let x = i; while (x) { a.unshift(x.menu_name); x = byId[x.parentId]; } return a.join('/'); };
  return { total: items.length, menus: items.map(i => ({ path: pathOf(i), url: i.url })) };
}

(async () => {
  const accounts = ['ybjcsgys1', 'ybjcsgys2', 'ybjcsgys3'];
  const out = [];
  for (const u of accounts) {
    try {
      const s = await loginHttp(u, passwordOf(u), '采购交易系统');
      const m = await menuOf(s);
      const survey = m.menus.filter(x => /市场调研|调研项目|参与调研|调研/.test(x.path));
      console.log(`OK ${u} | platform=${s.platform} | role=${s.role} | menus=${m.total}`);
      survey.forEach(x => console.log('   ', x.path, '->', x.url));
      out.push({ user: u, ok: true, platform: s.platform, role: s.role, menuTotal: m.total, survey });
    } catch (e) {
      console.log(`FAIL ${u}: ${e.message}`);
      out.push({ user: u, ok: false, error: e.message });
    }
  }
  fs.mkdirSync('explore/artifacts', { recursive: true });
  fs.writeFileSync('explore/artifacts/supplier-accounts-probe.json', JSON.stringify(out, null, 2));
})();
