"""「采购执行申请管理」页（S20）：草稿行【提交审批】→ 确定提交 → 状态“审批中”。

布局要点（openresty c29222ac，view/executionApply/list.html）：
- 列表在主框架 iframe，无页签，按“执行状态”筛选；操作列固定右列（表格不溢出时隐藏，点主表那份）；
- 【提交审批】先弹 top 确认框“确定提交采购执行申请进入审批流程吗？”，成功提示“操作成功！”并 reload；
- 页面不要求上传固定文书（前端无附件校验，后端校验已注释），草稿可直接提交。
"""
from __future__ import annotations

from core import browser as browser_helpers
from pages.common import READY_TIMEOUT_MS, confirm_or_msg, js_click

MODULE_URL = "/HospitalProcurement/view/executionApply/list.html"
MENU_ID = "approval-execution-apply"
MAIN_ROW = ".layui-table-view .layui-table-main tbody tr[data-index]"
FIXED_ROW = ".layui-table-view .layui-table-fixed-r tbody tr"


class ExecutionApplyPage:
    def __init__(self, session):
        self.session = session
        self.page = session.page
        browser_helpers.close_all_layers(self.page)
        self.frame = session.open_module(MODULE_URL, "采购执行申请管理", MENU_ID)
        self.frame.locator("#doSearch").wait_for(state="visible", timeout=READY_TIMEOUT_MS)

    def search(self, project_name: str) -> None:
        browser_helpers.close_all_layers(self.page)
        self.frame.locator('#searchBar input[idName="projectName"]').fill(project_name)
        self.frame.locator("#doSearch").click()
        self.frame.wait_for_timeout(1200)

    def find_row(self, project_name: str):
        cell = self.frame.locator('td[data-field="projectName"] .layui-table-cell',
                                  has_text=project_name)
        row = self.frame.locator(MAIN_ROW).filter(has=cell).first
        row.wait_for(state="visible", timeout=READY_TIMEOUT_MS)
        return row

    def state_of(self, project_name: str) -> str:
        return (self.find_row(project_name).locator('td[data-field="state"] span').inner_text()
                or "").strip()

    def submit(self, project_name: str) -> str:
        """提交草稿进入审批；返回提交后状态文案（审批中）。"""
        self.search(project_name)
        state = self.state_of(project_name)
        if "审批中" in state or "审批通过" in state:
            return state
        if "草稿" not in state and "驳回" not in state:
            raise AssertionError(f"执行申请状态为 {state!r}，不能提交审批")
        index = self.find_row(project_name).get_attribute("data-index")
        fixed = self.frame.locator(f'{FIXED_ROW}[data-index="{index}"] button[lay-event="submit"]')
        if fixed.count() > 0:
            js_click(fixed)
        else:
            js_click(self.find_row(project_name).locator('button[lay-event="submit"]'))
        kind, hint = confirm_or_msg(self.page, self.frame, timeout_ms=10000)
        if kind == "msg":
            raise AssertionError(f"提交执行申请被拦下：{hint}")
        if kind != "confirm":
            raise AssertionError("提交执行申请后未出现确认框")
        msg = browser_helpers.wait_for_msg(self.page, self.frame, timeout_ms=8000)
        if "操作成功" not in msg:
            raise AssertionError(f"提交执行审批未成功：{msg or '无提示信息'}")
        self.search(project_name)
        after = self.state_of(project_name)
        if "审批中" not in after:
            raise AssertionError(f"提交后执行申请状态应为审批中，实际 {after!r}")
        browser_helpers.close_all_layers(self.page)
        return after
