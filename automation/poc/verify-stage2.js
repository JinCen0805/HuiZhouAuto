// Verify: 申请单状态 + 调研项目是否自动生成
const path = require('path');
const { openSession, openModule } = require('../lib/hp-session');
const SHOT = path.join(__dirname, '..', 'shots');
const APP_NAME = process.env.APP_NAME || 'UI自动化前置测试-20261118070753';

(async () => {
  const s = await openSession('wanglun', '@Hc12345678');
  const apply = await openModule(s.page, '采购申请管理', '/HospitalProcurement/view/procurementApply/list.html', '0000006000001');
  await apply.waitForTimeout(2500);
  await apply.locator('.layui-tab-title li', { hasText: '申请单管理' }).first().click();
  await apply.waitForTimeout(2500);
  const row = apply.locator('.layui-table-view tr', { hasText: APP_NAME }).first();
  console.log('[申请单]', (await row.innerText().catch(() => '')).replace(/\s+/g, ' '));

  const survey = await openModule(s.page, '调研项目管理', '/HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyProject/list.html', '0000001000001');
  await survey.waitForTimeout(3000);
  const srow = survey.locator('.layui-table-view tr', { hasText: APP_NAME }).first();
  console.log('[调研项目]', (await srow.innerText().catch(() => '')).replace(/\s+/g, ' '));
  console.log('[调研页面]', (await survey.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 700));
  await s.page.screenshot({ path: path.join(SHOT, '72-survey-project-created.png') });
  await s.browser.close();
})().catch(e => { console.error('FAILED:', e); process.exit(1); });
