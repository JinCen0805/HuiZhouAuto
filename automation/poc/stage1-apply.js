// Stage 1 PoC: 采购申请发起 -> 保存草稿 -> 确认（进入待分配监督员）
const path = require('path');
const fs = require('fs');
const { openSession, openModule } = require('../lib/hp-session');

const SHOT = path.join(__dirname, '..', 'shots');
fs.mkdirSync(SHOT, { recursive: true });
const USER = process.env.HP_USER || 'wanglun';
const PASS = process.env.HP_PASS || '@Hc12345678';
const stamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
const PROJECT_NAME = 'UI自动化前置测试-' + stamp;

async function shot(page, name) { await page.screenshot({ path: path.join(SHOT, name) }); }

(async () => {
  const s = await openSession(USER, PASS);
  console.log('[ok] login', s.platform, '/', s.role);
  const frame = await openModule(s.page, '采购申请管理', '/HospitalProcurement/view/procurementApply/list.html', '0000006000001');
  await frame.waitForTimeout(2500);

  // 1. click 单独发起 on first enabled row
  const btn = frame.locator('button[lay-event="singleLaunch"]:not(.operation-disabled)').first();
  await btn.waitFor({ state: 'visible', timeout: 15000 });
  const rowText = await btn.locator('xpath=ancestor::tr').innerText().catch(() => '');
  console.log('[step1] click 单独发起 row:', rowText.replace(/\s+/g, ' ').slice(0, 200));
  await btn.click();
  await s.page.waitForTimeout(3500);

  const editFrame = s.page.frames().find(f => /procurementApply\/edit\.html/.test(f.url()));
  if (!editFrame) throw new Error('edit frame not found');
  console.log('[step2] edit frame:', editFrame.url());
  await shot(s.page, '50-edit-dialog.png');
  console.log('[layer btns]', (await s.page.locator('.layui-layer-btn').last().innerText().catch(() => '')).replace(/\s+/g, ' '));

  // 2. fill form
  await editFrame.waitForTimeout(1200);
  console.log('[form initial] projectName=', await editFrame.locator('[idName=projectName]').inputValue());
  console.log('[form initial] requestDepartment=', await editFrame.locator('[idName=requestDepartment]').inputValue());
  console.log('[form initial] attributeType=', await editFrame.locator('[idName=attributeType]').inputValue());
  await editFrame.fill('[idName=projectName]', PROJECT_NAME);
  await editFrame.selectOption('[idName=projectAttribute]', '1').catch(async () => {
    await editFrame.evaluate(() => {
      const el = document.querySelector('[idName=projectAttribute]');
      el.value = '1';
      el.dispatchEvent(new Event('change', { bubbles: true }));
    });
  });
  await editFrame.fill('[idName=purchaseContent]', '自动化测试采购内容：用于验证采购前置流程自动化的注射泵及相关配套耗材。');
  await editFrame.fill('[idName=applicationReason]', '自动化测试申请理由：科室现有设备老化，为保障临床业务正常开展，申请采购。');
  await editFrame.waitForTimeout(300);
  console.log('[form filled] projectAttribute=', await editFrame.locator('[idName=projectAttribute]').inputValue());
  await shot(s.page, '51-edit-filled.png');

  // 3. click 保存草稿 (layer button in parent page)
  const saveBtn = s.page.locator('.layui-layer-btn a', { hasText: '保存草稿' }).last();
  console.log('[step3] save btn count:', await saveBtn.count());
  await saveBtn.click();
  await s.page.waitForTimeout(4000);
  const msg = await s.page.locator('.layui-layer-msg').last().innerText().catch(() => '');
  console.log('[step3] msg after save:', msg.replace(/\s+/g, ' '));
  await shot(s.page, '52-after-save.png');
  // wait dialog close
  await s.page.waitForTimeout(3000);
  const editStill = s.page.frames().some(f => /procurementApply\/edit\.html/.test(f.url()));
  console.log('[step3] edit dialog still open:', editStill);

  // 4. switch to 申请单管理 tab and find draft
  const appTab = frame.locator('.layui-tab-title li', { hasText: '申请单管理' }).first();
  await appTab.click();
  await frame.waitForTimeout(3000);
  await shot(s.page, '53-applications-tab.png');
  const tableText = await frame.locator('.layui-table-view').last().innerText().catch(() => '');
  console.log('[step4] applications table:', tableText.replace(/\s+/g, ' ').slice(0, 1200));

  // find our row
  const ourRow = frame.locator('.layui-table-view tr', { hasText: PROJECT_NAME }).first();
  const ourCnt = await ourRow.count();
  console.log('[step4] our draft row count:', ourCnt);
  if (ourCnt > 0) {
    console.log('[step4] draft row:', (await ourRow.innerText()).replace(/\s+/g, ' '));
    await shot(s.page, '54-draft-row.png');
    const confirmBtn = ourRow.locator('button[lay-event="confirm"]');
    console.log('[step5] confirm btn count:', await confirmBtn.count());
    await confirmBtn.click();
    await s.page.waitForTimeout(1500);
    const dlgText = await s.page.locator('.layui-layer-dialog').last().innerText().catch(() => '');
    console.log('[step5] confirm dialog:', dlgText.replace(/\s+/g, ' '));
    await shot(s.page, '55-confirm-dialog.png');
    const okBtn = s.page.locator('.layui-layer-dialog .layui-layer-btn0, .layui-layer-btn a', { hasText: '确定' }).last();
    await okBtn.click();
    await s.page.waitForTimeout(4000);
    const msg2 = await s.page.locator('.layui-layer-msg').last().innerText().catch(() => '');
    console.log('[step5] msg after confirm:', msg2.replace(/\s+/g, ' '));
    await shot(s.page, '56-after-confirm.png');
    const rowAfter = frame.locator('.layui-table-view tr', { hasText: PROJECT_NAME }).first();
    console.log('[step5] row after confirm:', (await rowAfter.innerText().catch(() => '')).replace(/\s+/g, ' '));
  }
  console.log('[done] PROJECT_NAME=' + PROJECT_NAME);
  const finalRow = frame.locator('.layui-table-view tr', { hasText: PROJECT_NAME }).first();
  const finalText = await finalRow.innerText().catch(() => '');
  const codeMatch = finalText.match(/[A-Z]{2,}-[A-Z0-9]+-CG\d+/);
  const requestCode = codeMatch ? codeMatch[0] : '';
  console.log('[done] REQUEST_CODE=' + requestCode + ' | status row: ' + finalText.replace(/\s+/g, ' ').slice(0, 300));
  fs.writeFileSync(path.join(__dirname, '..', 'stage1-result.json'), JSON.stringify({ user: USER, projectName: PROJECT_NAME, requestCode, statusRow: finalText.replace(/\s+/g, ' '), ok: ourCnt > 0 }, null, 2));
  await s.browser.close();
})().catch(e => { console.error('FAILED:', e); process.exit(1); });
