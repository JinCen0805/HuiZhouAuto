"""纪检监察平台「监察项目列表」页（S04）：分配监督员。

布局要点（openresty c29222ac，view/projectList/index.{html,js}）：
- 列表页在平台壳 iframe 内；「分配监督员」弹窗由 window.top.layer 打开，DOM 在 top 文档；
- 操作列是 Layui 固定右列（表格溢出时会再渲染一份按钮，否则固定列隐藏、点主表那份）；
- 监督员下拉是 Layui 重绘 select：点 .layui-select-title 展开后点 dd[lay-value=userId]；
- 监督范围只有「全流程」一个选项且默认选中（name=assignSupervisionScope）。
"""
from __future__ import annotations

import re
import time

from core import browser as browser_helpers
from pages.common import READY_TIMEOUT_MS, js_click

LIST_URL = "/DisciplineInspection/view/projectList/index.html"
MENU_ID = "0000063000001"
GRID = "#projectGrid + .layui-table-view"
MAIN_ROW = f"{GRID} .layui-table-main tbody tr[data-index]"
FIXED_ROW = f"{GRID} .layui-table-fixed-r tbody tr"


class JjjcProjectPage:
    def __init__(self, session):
        self.session = session
        self.page = session.page
        browser_helpers.close_all_layers(self.page)
        self.frame = session.open_module(LIST_URL, "监察项目列表", MENU_ID)
        self.frame.locator("#keywordInput").wait_for(state="visible", timeout=READY_TIMEOUT_MS)

    def search(self, project_name: str) -> None:
        browser_helpers.close_all_layers(self.page)
        self.frame.fill("#keywordInput", project_name)
        self.frame.click("#btnSearch")
        self.frame.wait_for_timeout(1200)

    def find_row(self, project_name: str):
        """按项目名称精确匹配主表行（避免 R01 命中 R010）。"""
        cell = self.frame.locator(
            'td[data-field="projectName"] .layui-table-cell',
            has_text=re.compile(rf"^{re.escape(project_name)}$"),
        )
        row = self.frame.locator(MAIN_ROW).filter(has=cell).first
        row.wait_for(state="visible", timeout=READY_TIMEOUT_MS)
        return row

    def status_of(self, project_name: str) -> str:
        return (self.find_row(project_name)
                .locator('td[data-field="supervisionStatus"] .layui-table-cell')
                .inner_text() or "").strip()

    def assign_supervisor(self, project_name: str, supervisor_user_id: str,
                          supervisor_name: str = "") -> str:
        """行【分配监督员】→ 弹窗选监督员 → 全流程 → 确认分配；返回分配后状态文案。"""
        status = self.status_of(project_name)
        if "监察中" in status or "检查中" in status:
            return status
        if "待分配" not in status:
            raise AssertionError(f"项目状态为 {status!r}，不是待分配，不能分配监督员")
        index = self.find_row(project_name).get_attribute("data-index")
        # Layui 固定右列会再渲染一份按钮；用原生 click 触发，避免固定列隐藏/遮挡导致的可点性超时
        fixed = self.frame.locator(
            f'{FIXED_ROW}[data-index="{index}"] [lay-event="assignSupervisor"]'
        )
        if fixed.count() > 0:
            js_click(fixed)
        else:
            js_click(self.find_row(project_name).locator('[lay-event="assignSupervisor"]'))

        modal = self.page.locator(".di-assign-supervisor-modal")
        modal.wait_for(state="visible", timeout=READY_TIMEOUT_MS)
        shown = self.page.locator("#assignProjectName").input_value() or ""
        if shown.strip() != project_name.strip():
            raise AssertionError(f"分配弹窗带出的项目名不符：{shown!r} != {project_name!r}")

        # 监督员：Layui 重绘 select，点渲染节点展开后按 userId 选 dd
        select = self.page.locator("#assignSupervisorSelect + .layui-form-select")
        select.locator(".layui-select-title").click()
        option = select.locator(f'dl dd[lay-value="{supervisor_user_id}"]')
        option.first.wait_for(state="visible", timeout=10000)
        option.first.click()
        self.page.wait_for_function(
            "(id) => (document.querySelector('#assignSupervisorSelect') || {}).value === id",
            arg=supervisor_user_id, timeout=5000,
        )

        # 监督范围：唯一选项「全流程」默认已选；已选中时不要再点渲染节点（会取消选中）
        checked = self.page.locator("input[name='assignSupervisionScope']:checked")
        if checked.count() == 0:
            self.page.locator(".di-assign-supervisor-modal .layui-form-radio",
                              has_text="全流程").first.click()
            checked = self.page.locator("input[name='assignSupervisionScope']:checked")
        if (checked.first.get_attribute("value") or "") != "1":
            raise AssertionError("监督范围未选中「全流程」")

        self.page.locator("#btnConfirmAssignSupervisor").click()
        msg = browser_helpers.wait_for_msg(self.page, None, timeout_ms=8000)
        if "分配成功" not in msg:
            raise AssertionError(f"分配监督员未成功：{msg or '无提示信息'}")
        deadline = time.time() + 10
        while time.time() < deadline and modal.count() > 0:
            self.page.wait_for_timeout(200)

        self.search(project_name)
        after = self.status_of(project_name)
        if "监察中" not in after and "检查中" not in after:
            raise AssertionError(f"分配后列表状态应为监察中，实际 {after!r}")
        return after
