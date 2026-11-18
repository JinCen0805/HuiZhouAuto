// Explore stage 1: user info + selectable reserve rows + 单独发起 -> edit page form
const path = require('path');
const fs = require('fs');
const { openSession, openModule } = require('../lib/hp-session');

const SHOT = path.join(__dirname, '..', 'shots');
fs.mkdirSync(SHOT, { recursive: true });
const USER = process.env.HP_USER || 'cy-cbbm-jbr';
const PASS = process.env.HP_PASS || 'Hc1234';

(async () => {
  const s = await openSession(USER, PASS);
  console.log('platform:', s.platform, '| role:', s.role);
  const frame = await openModule(s.page, '采购申请管理', '/HospitalProcurement/view/procurementApply/list.html', '0000006000001');
  console.log('frame url:', frame && frame.url());
  await frame.waitForTimeout(3000);

  const info = await frame.evaluate(() => {
    try {
      const u = (typeof getUserBasicInfo === 'function') ? getUserBasicInfo() : (window.userBasicInfo || null);
      return u;
    } catch (e) { return { error: e.message }; }
  });
  console.log('USER INFO:', JSON.stringify(info));

  const rows = await frame.evaluate(() => {
    const out = [];
    document.querySelectorAll('#reserveLaunchTable + .layui-table-view tr, .layui-table-view tr').forEach(tr => {
      const cb = tr.querySelector('input.launch-reserve-checkbox');
      if (!cb) return;
      const tds = [...tr.querySelectorAll('td')].map(td => td.innerText.trim()).filter(Boolean);
      out.push({
        uuid: cb.getAttribute('data-uuid'),
        disabled: cb.disabled,
        blocked: cb.getAttribute('data-blocked'),
        title: cb.getAttribute('title'),
        owned: cb.getAttribute('data-owned'),
        cells: tds.slice(0, 10)
      });
    });
    return out;
  });
  console.log('ROWS:', JSON.stringify(rows, null, 1).slice(0, 4000));

  await s.page.screenshot({ path: path.join(SHOT, '40-apply-list-user.png') });

  // try click first enabled 单独发起 button
  const enabledBtn = frame.locator('button[lay-event="singleLaunch"]:not(.operation-disabled)').first();
  const cnt = await enabledBtn.count();
  console.log('enabled singleLaunch buttons:', cnt);
  if (cnt > 0) {
    await enabledBtn.click();
    await s.page.waitForTimeout(5000);
    console.log('URL after click:', s.page.url());
    await s.page.screenshot({ path: path.join(SHOT, '41-apply-edit.png') });
    const frames = s.page.frames().map(f => ({ name: f.name(), url: f.url().slice(0, 160) }));
    console.log('frames:', JSON.stringify(frames));
    for (const f of s.page.frames()) {
      if (/procurementApply\/(edit|list)/.test(f.url())) {
        const t = await f.locator('body').innerText().catch(() => '');
        console.log('FRAME', f.url(), ':', t.replace(/\s+/g, ' ').slice(0, 1500));
        fs.writeFileSync(path.join(__dirname, 'apply-edit-frame.html'), await f.content());
      }
    }
  } else {
    // dump per-row blocked reasons from table tooltips
    const reasons = await frame.evaluate(() => {
      const out = {};
      document.querySelectorAll('button[lay-event^="blockedSingleLaunch"]').forEach(b => {
        const r = b.getAttribute('title') || '?';
        out[r] = (out[r] || 0) + 1;
      });
      return out;
    });
    console.log('BLOCKED REASONS:', JSON.stringify(reasons, null, 1));
  }
  await s.browser.close();
})();
