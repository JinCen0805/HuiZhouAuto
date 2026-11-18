// Stage 2b PoC: 分包管理（UI）—— 新增子包 -> 保存 -> 确认分包
const path = require('path');
const fs = require('fs');
const { openSession, openModule } = require('../lib/hp-session');

const SHOT = path.join(__dirname, '..', 'shots');
fs.mkdirSync(SHOT, { recursive: true });
const APP_NAME = process.env.APP_NAME || 'UI自动化前置测试-20261118070753';
const REQUEST_CODE = process.env.REQUEST_CODE || 'HW-YXGZB-CG20260008';

async function shot(page, n) { await page.screenshot({ path: path.join(SHOT, n) }); }

(async () => {
  const s = await openSession('wanglun', '@Hc12345678');
  console.log('[ok] login', s.platform, '/', s.role);
  const frame = await openModule(s.page, '分包管理', '/HospitalProcurement/view/packageManagement/index.html', '0000006000002');
  await frame.waitForTimeout(3000);
  await shot(s.page, '60-package-list.png');
  console.log('[list]', (await frame.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 600));

  // filter by request name then search
  await frame.fill('[idName=requestName]', APP_NAME);
  await frame.click('#packageSearchBtn');
  await frame.waitForTimeout(2500);
  const row = frame.locator('.layui-table-view tr', { hasText: REQUEST_CODE }).first();
  const rowCnt = await row.count();
  console.log('[list] target row count:', rowCnt);
  if (!rowCnt) { console.log('[list] body:', (await frame.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 1500)); throw new Error('row not found'); }
  console.log('[list] row:', (await row.innerText()).replace(/\s+/g, ' '));
  const editBtn = row.locator('button[lay-event="edit"]');
  console.log('[list] 分包 button count:', await editBtn.count());
  await editBtn.click();
  await s.page.waitForTimeout(3500);
  await shot(s.page, '61-package-editor.png');

  const editor = s.page.frames().find(f => /packageManagement\/editor\/index\.html/.test(f.url()));
  if (!editor) throw new Error('editor frame not found; frames=' + JSON.stringify(s.page.frames().map(f => f.url())));
  console.log('[editor]', editor.url());
  await editor.waitForTimeout(1500);
  console.log('[editor] text:', (await editor.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 900));

  // 新增子包
  const addBtn = editor.locator('button[data-action="addPackage"]').first();
  console.log('[editor] addPackage btn:', await addBtn.count(), 'disabled:', await addBtn.getAttribute('aria-disabled'));
  await addBtn.click();
  await editor.waitForTimeout(1500);
  await shot(s.page, '62-subpackage-dialog.png');
  console.log('[dialog] title:', (await editor.locator('.layui-layer-title').last().innerText().catch(() => '')).trim());
  console.log('[dialog] item checkboxes:', await editor.locator('.package-item-select').count());
  const pkgName = '自动化子包-' + Date.now().toString().slice(-6);
  await editor.fill('#dialogPackageName', pkgName);
  // check first enabled item
  const firstCb = editor.locator('.package-item-select:not([disabled])').first();
  await firstCb.check({ force: true });
  await editor.waitForTimeout(600);
  console.log('[dialog] amount:', await editor.locator('#dialogPackageAmount').inputValue());
  const saveBtn = editor.locator('.layui-layer-btn a', { hasText: '保存' }).last();
  await saveBtn.click();
  await editor.waitForTimeout(3500);
  const msg1 = await editor.locator('.layui-layer-msg').last().innerText().catch(() => '');
  console.log('[dialog] save msg:', msg1.replace(/\s+/g, ' '));
  await shot(s.page, '63-subpackage-saved.png');
  const editorText = (await editor.locator('body').innerText()).replace(/\s+/g, ' ');
  console.log('[editor] text after save:', editorText.slice(0, 900));

  // 关闭分包编辑弹窗（确认锁定由 stage2c 在列表页完成）
  await editor.locator('#closeBtn').click().catch(() => {});
  fs.writeFileSync(path.join(__dirname, '..', 'stage2b-result.json'), JSON.stringify({
    appName: APP_NAME, requestCode: REQUEST_CODE, pkgName,
    subpackageCreated: /自动化子包-/.test(editorText)
  }, null, 2));
  await s.browser.close();
})().catch(e => { console.error('FAILED:', e); process.exit(1); });
