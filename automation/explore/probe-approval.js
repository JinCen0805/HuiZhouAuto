// Probe approval todo API with an approver account (zhaoliu)
const { loginHttp, BASE, getPassword } = require('../lib/hp-session');

function clientFrom(session) {
  return async (path, opts = {}) => {
    const headers = Object.assign({ Accept: 'application/json, text/javascript, */*; q=0.01', 'X-Requested-With': 'XMLHttpRequest', Cookie: session.cookies.map(c => `${c.name}=${c.value}`).join('; ') }, opts.headers || {});
    let body = opts.body;
    if (body && typeof body === 'object') { body = new URLSearchParams(body).toString(); headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'; }
    const res = await fetch(path.startsWith('http') ? path : BASE + path, { method: opts.method || (body ? 'POST' : 'GET'), headers, body, redirect: 'manual' });
    const text = await res.text(); let json = null; try { json = JSON.parse(text); } catch (e) {}
    return { status: res.status, text: text.slice(0, 500), json };
  };
}
(async () => {
  const s = await loginHttp('zhaoliu', getPassword('zhaoliu'), '采购交易系统');
  console.log('zhaoliu:', s.platform, s.role);
  const req = clientFrom(s);
  const g = await req('/EbiddingBusinessApproval/workflow/task/list/todo?current=1&size=10');
  console.log('GET todo:', g.status, g.text);
  const p = await req('/EbiddingBusinessApproval/workflow/task/list/todo', { body: { current: 1, size: 10 } });
  console.log('POST todo:', p.status, p.text);
  const g2 = await req('/EbiddingBusinessApproval/workflow/task/list/group/todo?current=1&size=10');
  console.log('GET group todo:', g2.status, g2.text);
})();
