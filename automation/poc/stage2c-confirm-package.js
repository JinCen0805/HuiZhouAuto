// Stage 2c PoC: 列表【确认】锁定分包 -> 验证 待调研 + 调研项目生成
const path = require('path');
const fs = require('fs');
const { openSession, openModule, BASE } = require('../lib/hp-session');

const SHOT = path.join(__dirname, '..', 'shots');
const APP_NAME = process.env.APP_NAME || 'UI自动化前置测试-20261118070753';
const REQUEST_CODE = process.env.REQUEST_CODE || 'HW-YXGZB-CG20260008';

(async () => {
  const s = await openSession('wanglun', '@Hc12345678');
  const frame = await openModule(s.page, '分包管理', '/HospitalProcurement/view/packageManagement/index.html', '0000006000002');
  await frame.waitForTimeout(2500);
  await frame.fill('[idName=requestName]', APP_NAME);
  await frame.click('#packageSearchBtn');
  await frame.waitForTimeout(2000);
  const row = frame.locator('.layui-table-view tr', { hasText: REQUEST_CODE }).first();
  console.log('[row]', (await row.innerText()).replace(/\s+/g, ' '));
  const confirmBtn = row.locator('button[lay-event="confirm"]');
  console.log('[row] confirm count:', await confirmBtn.count());
  await confirmBtn.click();
  await s.page.waitForTimeout(1500);
  // HCUI confirm dialog may be in top page or in list frame; search both
  const topDlg = s.page.locator('.layui-layer-dialog').last();
  const frameDlg = frame.locator('.layui-layer-dialog').last();
  let dlgText = '';
  if (await topDlg.count()) dlgText = await topDlg.innerText().catch(() => '');
  else if (await frameDlg.count()) dlgText = await frameDlg.innerText().catch(() => '');
  console.log('[confirm dialog]', dlgText.replace(/\s+/g, ' '));
  await s.page.screenshot({ path: path.join(SHOT, '70-package-confirm-dialog.png') });
  const okTop = s.page.locator('.layui-layer-dialog .layui-layer-btn0').last();
  const okFrame = frame.locator('.layui-layer-dialog .layui-layer-btn0').last();
  if (await okTop.count()) await okTop.click();
  else if (await okFrame.count()) await okFrame.click();
  else throw new Error('confirm ok button not found');
  await s.page.waitForTimeout(4000);
  console.log('[msg]', (await s.page.locator('.layui-layer-msg').last().innerText().catch(() => '')).replace(/\s+/g, ' '));
  await s.page.screenshot({ path: path.join(SHOT, '70b-package-confirmed.png') });

  // verify via list frame after refresh
  await frame.waitForTimeout(2000);
  const body = (await frame.locator('body').innerText()).replace(/\s+/g, ' ');
  console.log('[list after]', body.slice(0, 900));
  await s.page.screenshot({ path: path.join(SHOT, '71-package-after-confirm.png') });

  // verify via list API inside page context (same cookie)
  const api = await s.page.evaluate(async (name) => {
    const res = await fetch('/HospitalProcurement/hospitalPurchaseRequest/page?current=1&size=5&requestName=' + encodeURIComponent(name), { headers: { Accept: 'application/json' } });
    return await res.text();
  }, APP_NAME);
  console.log('[api page]', api.slice(0, 600));
  fs.writeFileSync(path.join(__dirname, '..', 'stage2c-result.json'), JSON.stringify({ requestCode: REQUEST_CODE, body, api }, null, 2));
  await s.browser.close();
})().catch(e => { console.error('FAILED:', e); process.exit(1); });
