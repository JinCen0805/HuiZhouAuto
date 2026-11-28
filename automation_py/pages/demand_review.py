"""「采购需求审查管理」页（S18）：干事发起审查 → 各审查人【审查】→ 选类型 → 一键通过 → 保存 → 确认通过。

布局要点（openresty c29222ac，view/procurementRequirementReview/{index,review/index}.{html,js}）：
- 列表页在主框架 iframe；选类型弹窗（.procurement-review-selection-dialog）、审查页 iframe 弹窗、
  所有 msg/confirm 都渲染在 **top 文档**；行操作按钮在固定右列（表格不溢出时点主表那份）；
- 审查页打开后会二次拉 taskDetail 重绘审查项，必须等重绘完成再点【一键通过】；
- 【保存】只存草稿并自动关闭审查页；回到选类型弹窗点【确认通过】（二次确认）才真正提交；
- 承办主任可勾审查类型（Layui checkbox 点渲染节点），职能部门/纪检的勾选框为 disabled；
- 左侧需求书 OnlyOffice 预览不参与保存，不需要等它。
"""
from __future__ import annotations

import time

from core import browser as browser_helpers
from pages.common import READY_TIMEOUT_MS, confirm_or_msg, js_click

MODULE_URL = "/HospitalProcurement/view/procurementRequirementReview/index.html"
MENU_ID = "approval-demand-review"
REVIEW_URL_PATTERN = "procurementRequirementReview/review/index.html"
SELECTION_DIALOG = ".procurement-review-selection-dialog"
MAIN_ROW = ".layui-table-view .layui-table-main tbody tr[data-index]"
FIXED_ROW = ".layui-table-view .layui-table-fixed-r tbody tr"


class DemandReviewPage:
    def __init__(self, session):
        self.session = session
        self.page = session.page
        browser_helpers.close_all_layers(self.page)
        self.frame = session.open_module(MODULE_URL, "采购需求审查管理", MENU_ID)
        self.frame.locator("#reviewSearchBtn").wait_for(state="visible", timeout=READY_TIMEOUT_MS)

    def search(self, request_code: str) -> None:
        browser_helpers.close_all_layers(self.page)
        self.frame.locator("#reviewRequestCode").fill(request_code)
        self.frame.locator("#reviewSearchBtn").click()
        self.frame.wait_for_timeout(1200)

    def find_row(self, request_code: str):
        cell = self.frame.locator('td[data-field="requestCode"] .layui-table-cell',
                                  has_text=request_code)
        row = self.frame.locator(MAIN_ROW).filter(has=cell).first
        row.wait_for(state="visible", timeout=READY_TIMEOUT_MS)
        return row

    def status_of(self, request_code: str) -> str:
        return (self.find_row(request_code).locator('td[data-field="reviewStatus"] .layui-table-cell')
                .inner_text() or "").strip()

    def _row_button(self, request_code: str, event: str):
        """返回行内按钮（优先固定右列那份），不存在返回 None。"""
        row = self.find_row(request_code)
        index = row.get_attribute("data-index")
        fixed = self.frame.locator(f'{FIXED_ROW}[data-index="{index}"] button[lay-event="{event}"]')
        if fixed.count() > 0 and fixed.first.is_visible():
            return fixed.first
        main = row.locator(f'button[lay-event="{event}"]')
        return main.first if main.count() > 0 else None
    def initiate(self, request_code: str) -> str:
        """承办干事【发起审查】（二次确认）→ 状态“审查中”。"""
        self.search(request_code)
        button = self._row_button(request_code, "startReview")
        if button is None:
            status = self.status_of(request_code)
            if "审查中" in status or "通过" in status:
                return status
            raise AssertionError(f"未出现【发起审查】按钮；状态 {status!r}")
        js_click(button)
        kind, msg = confirm_or_msg(self.page, self.frame, timeout_ms=10000)
        if kind != "confirm":
            raise AssertionError(f"发起审查未出现确认框：{msg or '无提示信息'}")
        msg = browser_helpers.wait_for_msg(self.page, self.frame, timeout_ms=8000)
        if "已发起" not in msg:
            raise AssertionError(f"发起审查未成功：{msg or '无提示信息'}")
        self.search(request_code)
        after = self.status_of(request_code)
        if "审查中" not in after:
            raise AssertionError(f"发起审查后状态应为审查中，实际 {after!r}")
        browser_helpers.close_all_layers(self.page)
        return after

    def review(self, request_code: str, timeout_s: int = 45, pick_general: bool = True) -> str:
        """审查人：行【审查】→（主任勾“一般性审查”）→ 进入审查 → 一键通过 → 保存 → 确认通过。"""
        deadline = time.time() + timeout_s
        while True:
            self.search(request_code)
            button = self._row_button(request_code, "review")
            if button is not None:
                break
            if time.time() >= deadline:
                raise AssertionError(f"未出现【审查】按钮；状态 {self.status_of(request_code)!r}")
            self.page.wait_for_timeout(1500)
        js_click(button)

        dialog = self.page.locator(SELECTION_DIALOG)
        dialog.wait_for(state="visible", timeout=READY_TIMEOUT_MS)
        # 等弹窗内的任务详情加载完（进入审查按钮可用）
        entry = dialog.locator('.review-entry-button[data-review-document="requirement"][data-review-mode="review"]')
        entry.wait_for(state="visible", timeout=READY_TIMEOUT_MS)

        if pick_general:
            row = dialog.locator('tr[data-document="requirement"]')
            checkbox = row.locator('input[value="general"]')
            if checkbox.count() > 0 and not checkbox.first.is_disabled() \
                    and not checkbox.first.is_checked():
                row.locator('.layui-form-checkbox', has_text="一般性审查").first.click()
                self.page.wait_for_function(
                    "() => { const el = document.querySelector(\".procurement-review-selection-dialog "
                    "tr[data-document='requirement'] input[value='general']\"); return !!el && el.checked; }",
                    timeout=5000,
                )

        with self.page.expect_response(
            lambda r: "/hospitalPurchaseDemandReview/taskDetail" in r.url, timeout=READY_TIMEOUT_MS
        ) as detail:
            entry.click()
        review = browser_helpers.get_frame(self.page, REVIEW_URL_PATTERN, timeout_ms=READY_TIMEOUT_MS)
        detail.value.finished()  # 审查页二次拉取详情后才会重绘审查项
        review.locator('#reviewQuestionList .review-question[data-question-id="general-1"]').wait_for(
            state="visible", timeout=READY_TIMEOUT_MS)
        review.wait_for_timeout(800)

        review.locator("#approveAllButtonGeneral").click()
        review.locator("#questionProgress", has_text="6/6").wait_for(timeout=10000)
        review.locator("#saveReviewButtonGeneral").click()
        # 保存成功后审查页自动关闭，选类型弹窗状态格变“已审查”
        deadline = time.time() + 20
        while time.time() < deadline and any(REVIEW_URL_PATTERN in f.url for f in self.page.frames):
            self.page.wait_for_timeout(200)
        dialog.locator('.review-status-cell[data-document="requirement"]', has_text="已审查") \
            .wait_for(timeout=15000)

        # 确认通过（二次确认）→ 真正提交
        js_click(dialog.locator(".layui-layer-btn0"))
        kind, hint = confirm_or_msg(self.page, self.frame, timeout_ms=10000)
        if kind == "msg":
            raise AssertionError(f"确认通过被前端校验拦下：{hint}")
        if kind != "confirm":
            raise AssertionError("确认通过后未出现确认框")
        msg = browser_helpers.wait_for_msg(self.page, self.frame, timeout_ms=8000)
        if "已确认通过" not in msg:
            raise AssertionError(f"确认通过未成功：{msg or '无提示信息'}")
        deadline = time.time() + 10
        while time.time() < deadline and dialog.count() > 0:
            self.page.wait_for_timeout(200)
        browser_helpers.close_all_layers(self.page)
        return msg
