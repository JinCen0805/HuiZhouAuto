"""HP 审计报告初稿在线编辑页（2026-11-24 承办主任复核流程）。

线上审计初稿必须在 OnlyOffice 编辑器里真实保存；本页直接打开 HP 的
`auditManagement/draftWorkflow.html`，注入弹窗参数后完成：
选模板 → 初始化报告 → 打开编辑器 → 点“保存报告” → 服务端确认已保存。
"""
from __future__ import annotations

import time

from core.config import Config


class AuditDraftPage:
    PATH = "/HospitalProcurement/view/auditManagement/draftWorkflow.html"

    def __init__(self, session, audit_id: str):
        self.session = session
        self.page = session.page
        self.audit_id = audit_id
        cfg = Config.load()
        self.page.goto(cfg.base_url + self.PATH, wait_until="domcontentloaded")
        self.page.wait_for_timeout(1500)
        # 正常入口由列表页弹窗注入该参数；直接打开时需要自己补上。
        self.page.evaluate(
            "(id) => { window.HCUI_LAYER_PARAENT_DATA = {auditId: id, mode: 'edit'}; }",
            audit_id,
        )
        self.page.evaluate("window.__init()")
        self.page.wait_for_timeout(800)

    def _state(self) -> str:
        try:
            return self.page.locator("#draftState").inner_text(timeout=5000)
        except Exception:  # noqa: BLE001
            return ""

    def _wait_until_loaded(self, timeout_s: int = 30) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            state = self._state()
            if state and "正在加载" not in state:
                return
            self.page.wait_for_timeout(500)
        raise RuntimeError(f"审计初稿页未加载完成：{self._state()[:200]}")

    def _open_editor(self) -> None:
        """把已有报告或新模板打开到 OnlyOffice 编辑器。"""
        edit_button = self.page.locator(
            "#draftSelectedReportRows button[data-action='edit']")
        if edit_button.count() > 0 and edit_button.first.is_visible():
            edit_button.first.click()
            return

        radios = self.page.locator("#draftTemplateRows input[name='draftTemplate']")
        deadline = time.time() + 20
        while radios.count() == 0 and time.time() < deadline:
            self.page.wait_for_timeout(500)
        if radios.count() == 0:
            raise RuntimeError(f"没有可用的审计报告模板：{self._state()[:200]}")
        radios.first.check(force=True)
        self.page.locator("#draftOpen").click()

    def _save_frame(self):
        """编辑器可能在当前页，也可能在 HCUI 弹窗 iframe 中。"""
        for frame in [self.page] + list(self.page.frames):
            try:
                button = frame.locator("#draftSave")
                if button.count() > 0 and button.first.is_visible():
                    return frame, button.first
            except Exception:  # noqa: BLE001 - 跨域/已销毁 frame 忽略
                continue
        return None, None

    def ensure_report_saved(self) -> None:
        from api.document_api import audit_report_detail

        self._wait_until_loaded()
        self._open_editor()

        frame = button = None
        deadline = time.time() + 90
        while time.time() < deadline:
            frame, button = self._save_frame()
            if frame is not None:
                break
            self.page.wait_for_timeout(1000)
        if frame is None:
            raise RuntimeError(f"未找到“保存报告”按钮：{self._state()[:200]}")

        # 编辑器 onDocumentReady 前按钮是 disabled 的
        deadline = time.time() + 120
        while time.time() < deadline:
            if button.is_enabled():
                break
            self.page.wait_for_timeout(1000)
        if not button.is_enabled():
            raise RuntimeError(f"OnlyOffice 编辑器未就绪：{self._state()[:200]}")

        button.click()
        deadline = time.time() + 90
        while time.time() < deadline:
            detail = audit_report_detail(self.session, self.audit_id)
            report = detail.get("report") or {}
            if int(report.get("reportStatus") or 0) == 2 and detail.get("saved"):
                print("[S16] 审计报告初稿已保存（OnlyOffice 在线编辑器）")
                return
            self.page.wait_for_timeout(1000)
        raise RuntimeError(f"在线编辑器保存后报告仍未变为已保存：{self._state()[:200]}")
