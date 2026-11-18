"""审计审理页（纪检平台）：选择模板 → 保存审计报告 → 提交主任审批。"""
from __future__ import annotations

from core import browser as browser_helpers
from core.config import Config

REVIEW_PATH = "/DisciplineInspection/view/purchaseAudit/review.html?auditId="
EDITOR_URL_PATTERN = "purchaseAudit/reportEditor.html"


class AuditReviewPage:
    def __init__(self, session, audit_id: str):
        self.session = session
        self.page = session.page
        cfg = Config.load()
        self.page.goto(cfg.base_url + REVIEW_PATH + audit_id, wait_until="domcontentloaded")
        self.page.locator("#chooseTemplateBtn").wait_for(state="visible", timeout=20000)
        self.page.wait_for_timeout(1000)

    # ── 审计报告保存（OnlyOffice 编辑器）──────────────────────
    def ensure_report_saved(self) -> None:
        report_info = self.page.locator("#reportInfo").inner_text()
        if "已保存" in report_info:
            print("[S16] 审计报告已是已保存状态")
            return
        edit_button = self.page.locator("#reportInfo .report-edit")
        if edit_button.count() > 0:
            edit_button.first.click()
        else:
            self.page.locator("#chooseTemplateBtn").click()
            dialog = self.page.locator(".layui-layer-page:has-text('选择审计报告模板')").last
            dialog.wait_for(state="visible", timeout=10000)
            radios = dialog.locator("input[name='auditTemplate']")
            if radios.count() == 0:
                raise LookupError("没有可用的审计报告模板")
            radios.first.check(force=True)
            dialog.locator(".layui-layer-btn0").last.click()

        editor = browser_helpers.get_frame(self.page, EDITOR_URL_PATTERN, timeout_ms=30000)
        editor.locator("#saveReportBtn").wait_for(state="visible", timeout=60000)
        # 等 OnlyOffice 初始化完成（状态文本变为“可编辑”，或按钮可用）
        editor.wait_for_function(
            """() => {
                const btn = document.querySelector('#saveReportBtn');
                const state = document.querySelector('#state');
                return !!btn && !btn.disabled
                    && ((state && /可编辑/.test(state.innerText || '')) || !btn.disabled);
            }""",
            timeout=90000,
        )
        editor.locator("#saveReportBtn").click()
        for _ in range(180):
            if not any(EDITOR_URL_PATTERN in f.url for f in self.page.frames):
                break
            text = editor.locator("#state").inner_text() if any(
                EDITOR_URL_PATTERN in f.url for f in self.page.frames) else "已关闭"
            if "已保存" in text or "正在关闭" in text:
                break
            editor.wait_for_timeout(500)
        self.page.wait_for_timeout(1500)
        print("[S16] 审计报告已触发保存")

    # ── 提交主任审批 ─────────────────────────────────────────
    def submit_review(self, opinion: str) -> None:
        self.page.fill("#auditOpinion", opinion)
        self.page.locator("#saveBtn").click()
        self.page.wait_for_timeout(2500)
