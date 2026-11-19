"""审计审理页（纪检平台）：选择模板 → 保存审计报告 → 提交主任审批。"""
from __future__ import annotations

from core import browser as browser_helpers
from core.config import Config

REVIEW_PATH = "/DisciplineInspection/view/purchaseAudit/review.html?auditId="
EDITOR_URL_PATTERN = "purchaseAudit/reportEditor.html"


class AuditReviewPage:
    def __init__(self, session, audit_id: str):
        self.session = session
        self.audit_id = audit_id
        self.page = session.page
        cfg = Config.load()
        self.page.goto(cfg.base_url + REVIEW_PATH + audit_id, wait_until="domcontentloaded")
        self.page.locator("#chooseTemplateBtn").wait_for(state="visible", timeout=20000)
        self.page.wait_for_timeout(1000)

    # ── 审计报告保存（OnlyOffice 编辑器）──────────────────────
    def _report_status(self) -> int:
        from api.audit_api import AuditApi

        try:
            data = AuditApi(self.session).review(self.audit_id)
        except Exception:
            return 0
        report = data.get("report") or (data.get("reports") or [{}])[0]
        return int(report.get("reportStatus") or 0)

    def ensure_report_saved(self) -> None:
        status = self._report_status()
        if status == 2:
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
        # 等 OnlyOffice 真正初始化完成：状态文本必须变“可编辑”
        editor.wait_for_function(
            """() => {
                const state = document.querySelector('#state');
                const btn = document.querySelector('#saveReportBtn');
                return !!btn && !!state && /可编辑/.test(state.innerText || '');
            }""",
            timeout=120000,
        )
        editor.wait_for_timeout(1500)
        editor.locator("#saveReportBtn").click()

        for _ in range(120):  # 最多 60s
            if self._report_status() == 2:
                print("[S16] 审计报告已保存（服务端确认 reportStatus=2）")
                return
            self.page.wait_for_timeout(500)
        # 仍未保存：若编辑器还在，重试一次保存
        if any(EDITOR_URL_PATTERN in f.url for f in self.page.frames):
            try:
                editor.locator("#saveReportBtn").click()
            except Exception:
                pass
            for _ in range(60):
                if self._report_status() == 2:
                    print("[S16] 审计报告已保存（重试后服务端确认）")
                    return
                self.page.wait_for_timeout(500)
        raise RuntimeError("审计报告保存失败：OnlyOffice 编辑器未把报告保存为 reportStatus=2")

    # ── 提交主任审批 ─────────────────────────────────────────
    def submit_review(self, opinion: str) -> None:
        self.page.fill("#auditOpinion", opinion)
        self.page.locator("#saveBtn").click()
        self.page.wait_for_timeout(2500)
