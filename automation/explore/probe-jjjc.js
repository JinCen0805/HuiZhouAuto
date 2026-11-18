// Probe 纪检平台: supervisorList, projectPageList, assign; verify HP status persistence.
const { loginHttp, BASE, md5, getPassword } = require('../lib/hp-session');
const fs = require('fs');

function clientFrom(session) {
  return async (path, opts = {}) => {
    const headers = Object.assign({ Accept: 'application/json, text/javascript, */*; q=0.01', 'X-Requested-With': 'XMLHttpRequest', Cookie: session.cookies.map(c => `${c.name}=${c.value}`).join('; ') }, opts.headers || {});
    let body = opts.body;
    if (body && typeof body === 'object' && !opts.json) { body = new URLSearchParams(body).toString(); headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'; }
    if (opts.json && typeof body === 'object') { body = JSON.stringify(body); headers['Content-Type'] = 'application/json; charset=UTF-8'; }
    const res = await fetch(path.startsWith('http') ? path : BASE + path, { method: opts.method || (body ? 'POST' : 'GET'), headers, body, redirect: 'manual' });
    const text = await res.text(); let json = null; try { json = JSON.parse(text); } catch (e) {}
    return { status: res.status, text, json, headers: res.headers };
  };
}

(async () => {
  const jj = await loginHttp('jjzr', getPassword('jjzr'), '纪检监察平台');
  console.log('jjzr platform:', jj.platform, '| role:', jj.role, '| target:', jj.target);
  const req = clientFrom(jj);
  const sup = await req('/jjjc/supervise/supervisorList?prjCode=prjCode_PR_JJJC&pageNum=1&pageSize=50');
  console.log('supervisorList:', sup.status, JSON.stringify(sup.json).slice(0, 1500));
  const proj = await req('/jjjc/supervise/projectPageList?prjCode=prjCode_PR_JJJC&supervisionStatus=&pageNum=1&pageSize=10');
  console.log('projectPageList:', proj.status, JSON.stringify(proj.json).slice(0, 1500));
  const can = await req('/jjjc/supervise/canManageAssignment');
  console.log('canManage:', can.status, can.text);
  fs.writeFileSync('jjjc-probe.json', JSON.stringify({ sup: sup.json, proj: proj.json, can: can.json }, null, 2));
})();
