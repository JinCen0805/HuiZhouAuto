"""审批工作台「待办/已办」页：通用办理（BT14 / BT6 / BT13 等所有审批节点）。

布局要点（openresty c29222ac）：
- 三层 iframe：主框架 → iframe.mainIframe[name="采购工作台"]（procurementWorkbench/index.html#task-center?view=todo）
  → iframe.pwb-shell__frame[data-module-id="task-center"] → 待办列表 iframe（businessApproval/personal/todoTaskList.html）；
- 点行内【办理】（a[lay-event="toComplete"]）后，弹窗挂在 **top 文档**：
  div.layui-layer[hcui_pop_name="completedTab"] > iframe（businessApproval/personal/toCompletePage.html），
  底部【提交】.layui-layer-btn0 / 【返回】.layui-layer-btn1；提交前有 layer.confirm 二次确认；
- 弹窗内：审核结果 radio name=auditResult（Layui 重绘，点 + .layui-form-radio）、意见 #commentTextarea、
  BT6 采购办节点出现评标方式 select#bidEvaluationFormSelect（选“通过”后才显示）、
  BT13 采购办节点出现选人 select#handlerUserSelect（候选异步加载后会重绘）；
- BT13 待办行没有申请单号列，因此用“拦截待办列表响应 → 按 taskId 找 records 下标 = 行 data-index”定位。
"""
from __future__ import annotations

import time

from core import browser as browser_helpers
from pages.common import READY_TIMEOUT_MS, confirm_or_msg, js_click

WORKBENCH_URL = ("/HospitalProcurement/view/procurementWorkbench/index.html"
                 "#task-center?view=todo")
TODO_URL_PATTERN = "businessApproval/personal/todoTaskList.html"
DIALOG_URL_PATTERN = "businessApproval/personal/toCompletePage.html"
DIALOG_SELECTOR = 'div.layui-layer[hcui_pop_name="completedTab"]'
TODO_LIST_API = "/EbiddingBusinessApproval/workflow/task/list/todo"


class ApprovalWorkbenchPage:
    def __init__(self, session):
        self.session = session
        self.page = session.page
        browser_helpers.close_all_layers(self.page)
        self.frame = session.open_module(WORKBENCH_URL, "采购工作台", "approval-workbench-todo")
        self.todo = browser_helpers.get_frame(self.page, TODO_URL_PATTERN, timeout_ms=READY_TIMEOUT_MS)
        self.todo.locator("#searchBtn").wait_for(state="visible", timeout=READY_TIMEOUT_MS)
        self.dialog = None

    # ── 待办列表 ─────────────────────────────────────────────
    def reload_todo(self, timeout_ms: int = READY_TIMEOUT_MS) -> list[dict]:
        """点【搜索】并拦截列表响应，返回 records（下标即表格行 data-index）。"""
        with self.page.expect_response(lambda r: TODO_LIST_API in r.url, timeout=timeout_ms) as info:
            self.todo.locator("#searchBtn").click()
        body = info.value.json() or {}
        if not body.get("success"):
            raise RuntimeError(f"待办列表查询失败：{str(body)[:300]}")
        return (body.get("data") or {}).get("records") or []

    def row_index_of(self, task_id: str, timeout_s: int = 40) -> int:
        """在待办列表中找到指定 taskId 的行下标（列表按需刷新，最多等 timeout_s）。"""
        deadline = time.time() + timeout_s
        last = []
        while True:
            last = self.reload_todo()
            for i, row in enumerate(last):
                if str(row.get("id")) == str(task_id):
                    self.todo.locator(
                        f'.layui-table-main tbody tr[data-index="{i}"]'
                    ).wait_for(state="visible", timeout=READY_TIMEOUT_MS)
                    return i
            if time.time() >= deadline:
                names = [f"{r.get('id')}:{r.get('name')}" for r in last[:10]]
                raise LookupError(f"待办列表未找到任务 {task_id}；当前：{names}")
            self.page.wait_for_timeout(1500)

    # ── 办理弹窗 ─────────────────────────────────────────────
    def open_dialog(self, index: int):
        # 原生 click：Layui 固定列在滚动/不溢出时会隐藏，普通 click 会反复等待可见性直至超时
        fixed = self.todo.locator(
            f'.layui-table-fixed-r tr[data-index="{index}"] a[lay-event="toComplete"]'
        )
        if fixed.count() > 0:
            js_click(fixed)
        else:
            js_click(self.todo.locator(
                f'.layui-table-main tbody tr[data-index="{index}"] a[lay-event="toComplete"]'
            ))
        self.page.locator(DIALOG_SELECTOR).wait_for(state="visible", timeout=READY_TIMEOUT_MS)
        dialog = browser_helpers.get_frame(self.page, DIALOG_URL_PATTERN)
        dialog.locator("#formTable").wait_for(state="visible", timeout=READY_TIMEOUT_MS)
        return dialog

    @staticmethod
    def _select_layui_option(frame, select_selector: str, value: str, timeout_ms: int = 15000) -> None:
        """Layui 重绘 select：点渲染节点展开后点 dd[lay-value]。候选异步加载时等待 option 出现。"""
        option = frame.locator(f"{select_selector} + .layui-form-select dl dd[lay-value='{value}']")
        option.first.wait_for(state="attached", timeout=timeout_ms)
        box = frame.locator(f"{select_selector} + .layui-form-select")
        box.locator(".layui-select-title").click()
        option.first.click()
        frame.wait_for_function(
            "([s, v]) => (document.querySelector(s) || {}).value === v",
            arg=[select_selector, value], timeout=5000,
        )

    def fill_dialog(self, dialog, comment: str, bid_evaluation_form: str = "",
                    handler_user_id: str = "") -> None:
        # 审核结果：通过（原生 radio 被 Layui 隐藏，点渲染节点）
        radio = 'input[name="auditResult"][value="1"]'
        dialog.locator(f"{radio} + .layui-form-radio").first.click()
        dialog.wait_for_function(
            "(s) => { const el = document.querySelector(s); return !!el && el.checked; }",
            arg=radio, timeout=5000,
        )
        if comment:
            dialog.fill("#commentTextarea", comment)
        if bid_evaluation_form:
            row = dialog.locator("tr.bid-evaluation-form-row")
            row.wait_for(state="visible", timeout=10000)
            self._select_layui_option(dialog, "#bidEvaluationFormSelect", bid_evaluation_form)
        if handler_user_id:
            handler = dialog.locator("#handlerUserSelect")
            handler.wait_for(state="attached", timeout=15000)
            self._select_layui_option(dialog, "#handlerUserSelect", handler_user_id)

    def submit_dialog(self, dialog) -> str:
        """点弹窗底部【提交】→ 二次确认【确定】→ 等“办理成功”且弹窗关闭。"""
        js_click(self.page.locator(f"{DIALOG_SELECTOR} .layui-layer-btn0"))
        kind, hint = confirm_or_msg(self.page, dialog, timeout_ms=10000)
        if kind == "msg":
            raise AssertionError(f"审批提交被前端校验拦下：{hint}")
        if kind != "confirm":
            raise AssertionError("审批提交后未出现确认框")
        msg = browser_helpers.wait_for_msg(self.page, dialog, timeout_ms=8000)
        if "办理成功" not in msg:
            raise AssertionError(f"审批提交未成功：{msg or '无提示信息'}")
        deadline = time.time() + 15
        while time.time() < deadline and self.page.locator(DIALOG_SELECTOR).count() > 0:
            self.page.wait_for_timeout(200)
        return msg

    def complete(self, task_id: str, comment: str, bid_evaluation_form: str = "",
                 handler_user_id: str = "") -> str:
        """办理一条待办：定位行 → 办理 → 通过（按需选评标方式/经办人）→ 提交。返回提示文案。"""
        index = self.row_index_of(task_id)
        dialog = self.open_dialog(index)
        self.fill_dialog(dialog, comment, bid_evaluation_form=bid_evaluation_form,
                         handler_user_id=handler_user_id)
        msg = self.submit_dialog(dialog)
        browser_helpers.close_all_layers(self.page)
        return msg
