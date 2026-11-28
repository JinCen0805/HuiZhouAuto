"""「采购方式分配」页（S19）：待分配申请行【分配方式】→ 弹窗选类别/方式/议比价方式/依据/纪要 → 推送主任审批。

布局要点（openresty c29222ac，view/procurementMethodConfirm/{index,editor/index}.{html,js}）：
- 列表页在主框架 iframe；编辑弹窗 iframe 与底部按钮（【推送主任审批】/【关闭】）挂在 **top 文档**；
- 待分配页签筛选为纯前端过滤；行操作按钮在固定右列（表格不溢出时固定列隐藏，点主表那份）；
- 采购类别按“是否涉及政府采购”锁定（disabled，不可改）；采购方式/议比价方式为 Layui 重绘 select，
  每次变更后 form.render 会重建渲染节点，需重新定位；
- 自主采购 + 唯一来源谈判时出现【添加】纪要按钮，上传走页面 WebUploader（隐藏的 input[type=file]）；
- 【推送主任审批】→ 二次确认“确认推送采购方式至承办部门主任审批吗”→ 提示“采购方式已分配并推送主任审批”。
"""
from __future__ import annotations

import time

from core import browser as browser_helpers
from pages.common import READY_TIMEOUT_MS, confirm_or_msg, js_click

MODULE_URL = "/HospitalProcurement/view/procurementMethodConfirm/index.html"
MENU_ID = "approval-method-confirm"
EDITOR_URL_PATTERN = "procurementMethodConfirm/editor/index.html"
GRID = "#candidateTable + .layui-table-view"
MAIN_ROW = f"{GRID} .layui-table-main tbody tr[data-index]"
FIXED_ROW = f"{GRID} .layui-table-fixed-r tbody tr"


class ProcurementMethodPage:
    def __init__(self, session):
        self.session = session
        self.page = session.page
        browser_helpers.close_all_layers(self.page)
        self.frame = session.open_module(MODULE_URL, "采购方式分配", MENU_ID)
        self.frame.locator("#candidateSearchBtn").wait_for(state="visible", timeout=READY_TIMEOUT_MS)
        self.frame.locator(".method-tabs li[lay-id='candidate']").click()
        self.frame.wait_for_timeout(1200)

    def search(self, request_code: str) -> None:
        browser_helpers.close_all_layers(self.page)
        self.frame.locator('#candidateSearchForm input[idName="requestCode"]').fill(request_code)
        self.frame.locator("#candidateSearchBtn").click()
        self.frame.wait_for_timeout(1000)

    def find_row(self, request_code: str):
        cell = self.frame.locator('td[data-field="requestCode"] .layui-table-cell',
                                  has_text=request_code)
        row = self.frame.locator(MAIN_ROW).filter(has=cell).first
        row.wait_for(state="visible", timeout=READY_TIMEOUT_MS)
        return row

    def _click_row_button(self, index: int, row, event: str) -> None:
        fixed = self.frame.locator(f'{FIXED_ROW}[data-index="{index}"] button[lay-event="{event}"]')
        if fixed.count() > 0:
            js_click(fixed)
        else:
            js_click(row.locator(f'button[lay-event="{event}"]'))

    @staticmethod
    def _select(frame, select_selector: str, value: str) -> None:
        """Layui select：点渲染节点展开 → 点 dd[lay-value] → 校验原生 select 值。"""
        option = frame.locator(f"{select_selector} + .layui-form-select dl dd[lay-value='{value}']")
        option.first.wait_for(state="attached", timeout=10000)
        frame.locator(f"{select_selector} + .layui-form-select .layui-select-title").click()
        option.first.click()
        frame.wait_for_function(
            "([s, v]) => (document.querySelector(s) || {}).value === v",
            arg=[select_selector, value], timeout=5000,
        )
        # 变更后 form.render('select') 会重建渲染节点，等新节点就位
        frame.locator(f"{select_selector} + .layui-form-select .layui-select-title").wait_for(
            state="visible", timeout=10000)

    def assign(self, request_code: str, category: str, method: str, basis: str,
               in_hospital_price_type: str = "", attachment_path: str = "") -> str:
        """分配采购方式并推送主任审批；返回成功提示文案。"""
        self.search(request_code)
        row = self.find_row(request_code)
        index = row.get_attribute("data-index")
        blocked = self.frame.locator(f'{FIXED_ROW}[data-index="{index}"] button[lay-event="blockedAssign"]')
        if blocked.count() == 0:
            blocked = row.locator('button[lay-event="blockedAssign"]')
        if blocked.count() > 0:
            raise AssertionError(f"该申请当前不能分配方式：{blocked.first.get_attribute('title')}")
        self._click_row_button(index, row, "assign")

        editor = browser_helpers.get_frame(self.page, EDITOR_URL_PATTERN, timeout_ms=READY_TIMEOUT_MS)
        editor.locator("#purchaseCategory + .layui-form-select .layui-select-title input").wait_for(
            state="visible", timeout=READY_TIMEOUT_MS)

        # 采购类别：按是否涉及政府采购锁定，不可改；未锁定且不符时才选
        locked = editor.locator("#purchaseCategory").is_disabled()
        current = editor.locator("#purchaseCategory").input_value() if not locked else \
            editor.evaluate("() => document.querySelector('#purchaseCategory').value")
        if str(current) != str(category):
            if locked:
                raise AssertionError(f"采购类别已锁定为 {current!r}，与期望 {category!r} 不符")
            self._select(editor, "#purchaseCategory", str(category))

        self._select(editor, "#purchaseMethod", str(method))

        if in_hospital_price_type:
            editor.locator("#inHospitalPriceTypeField").wait_for(state="visible", timeout=10000)
            self._select(editor, "#inHospitalPriceType", str(in_hospital_price_type))

        if attachment_path:
            editor.locator("#addMethodAttachmentBtn").wait_for(state="visible", timeout=10000)
            editor.locator("#methodAttachmentUploader #methodAttachmentFilePicker input[type=file]") \
                .set_input_files(attachment_path)
            editor.locator("#attachmentRows", has_text="唯一性论证会议纪要").wait_for(
                timeout=60000)

        editor.locator('#methodForm textarea[idName="procurementBasis"]').fill(basis)

        # 顶层【推送主任审批】（iframe 弹窗 class 为 layui-layer-iframe）→ 二次确认或校验提示。
        # 附件上传完成标志是页面内部变量（无 DOM 信号），被“正在上传”拦下时短等重试。
        push = self.page.locator(".layui-layer .layui-layer-btn .layui-layer-btn0",
                                 has_text="推送主任审批")
        kind, msg = "", ""
        for _attempt in range(6):
            js_click(push)
            kind, msg = confirm_or_msg(self.page, editor, timeout_ms=12000)
            if kind == "confirm":
                break
            if kind == "msg" and "正在上传" in msg:
                time.sleep(1.5)
                continue
            break
        if kind == "msg":
            raise AssertionError(f"推送采购方式被前端校验拦下：{msg}")
        if kind != "confirm":
            raise AssertionError("推送采购方式后未出现确认框")
        msg = browser_helpers.wait_for_msg(self.page, editor, timeout_ms=8000)
        if "已分配并推送" not in msg and "重新推送" not in msg:
            raise AssertionError(f"推送采购方式审批未成功：{msg or '无提示信息'}")
        deadline = time.time() + 15
        while time.time() < deadline and any(EDITOR_URL_PATTERN in f.url for f in self.page.frames):
            self.page.wait_for_timeout(200)
        browser_helpers.close_all_layers(self.page)
        return msg
