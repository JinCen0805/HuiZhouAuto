// Stage 2a PoC: 纪检主任分配监督员（API，跨系统），验证申请单 22 -> 8
const { loginHttp, BASE, getPassword } = require('../lib/hp-session');
const fs = require('fs');

function clientFrom(session, opts = {}) {
  return async (path, options = {}) => {
    const headers = Object.assign({
      Accept: 'application/json, text/javascript, */*; q=0.01',
      'X-Requested-With': 'XMLHttpRequest',
      Cookie: session.cookies.map(c => `${c.name}=${c.value}`).join('; ')
    }, options.headers || {});
    let body = options.body;
    if (options.json && typeof body === 'object') {
      body = JSON.stringify(body);
      headers['Content-Type'] = 'application/json; charset=UTF-8';
    } else if (body && typeof body === 'object') {
      body = new URLSearchParams(body).toString();
      headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8';
    }
    const res = await fetch(path.startsWith('http') ? path : BASE + path, {
      method: options.method || (body ? 'POST' : 'GET'), headers, body, redirect: 'manual'
    });
    const text = await res.text();
    let json = null; try { json = JSON.parse(text); } catch (e) {}
    return { status: res.status, text, json };
  };
}

const APP_NAME = process.env.APP_NAME || 'UI自动化前置测试-20261118070753';

(async () => {
  const jj = await loginHttp('jjzr', getPassword('jjzr'), '纪检监察平台');
  const jreq = clientFrom(jj);
  const sup = await jreq('/jjjc/supervise/supervisorList?prjCode=prjCode_PR_JJJC&pageNum=1&pageSize=50');
  const candidates = (sup.json && sup.json.data) || [];
  console.log('supervisor candidates:', candidates.length);
  candidates.slice(0, 8).forEach(c => console.log(' -', c.supervisorUserId, c.userName, c.legalContact, c.departmentName, c.onDutyStatus, 'current=' + c.currentProjectCount));
  const usable = candidates.filter(c => c.supervisorUserId && c.onDutyStatus === '在岗');
  const supervisor = usable[0];
  if (!supervisor) throw new Error('no usable supervisor');

  const proj = await jreq('/jjjc/supervise/projectPageList?prjCode=prjCode_PR_JJJC&projectName=' + encodeURIComponent(APP_NAME) + '&pageNum=1&pageSize=10');
  const rows = (proj.json && proj.json.data) || [];
  const target = rows.find(r => r.requestName === APP_NAME) || rows[0];
  if (!target) throw new Error('project not found in supervision list');
  console.log('target project:', target.uuid, target.requestCode, target.requestName, 'status=' + target.requestStatus, target.supervisionStatus);

  const assign = await jreq('/jjjc/supervise/assign', {
    method: 'POST', json: true,
    body: { projectId: target.uuid, supervisorUserId: supervisor.supervisorUserId, supervisionScope: '1' }
  });
  console.log('assign result:', assign.status, assign.text.slice(0, 300));

  const proj2 = await jreq('/jjjc/supervise/projectPageList?prjCode=prjCode_PR_JJJC&projectName=' + encodeURIComponent(APP_NAME) + '&pageNum=1&pageSize=10');
  const t2 = ((proj2.json && proj2.json.data) || [])[0];
  console.log('after assign:', t2 && { requestStatus: t2.requestStatus, supervisionStatus: t2.supervisionStatus, supervisorName: t2.supervisorName, supervisionScope: t2.supervisionScope });

  fs.writeFileSync('stage2a-result.json', JSON.stringify({ appName: APP_NAME, supervisor, target, assign: assign.json, after: t2 }, null, 2));
})();
