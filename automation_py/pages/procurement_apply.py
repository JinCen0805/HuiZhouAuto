"""采购申请管理页（S01）：发起采购申请 → 保存草稿 → 确认。"""
from __future__ import annotations

from core import browser as browser_helpers
from pages.common import click_row_event, find_row_by_text, wait_table_rows

MODULE_URL = "/HospitalProcurement/view/procurementApply/list.html"
MENU_ID = "0000006000001"


class ProcurementApplyPage:
    def __init__(self, session):
        self.session = session
        self.page = session.page
        self.frame = session.open_module(MODULE_URL, "采购申请管理", MENU_ID)
        # 默认“发起采购申请”页签，等待可发起的预算计划按钮出现
        self.frame.locator("button[lay-event='singleLaunch']").first.wait_for(
            state="visible", timeout=20000
        )

    # ── 发起采购申请 ─────────────────────────────────────────
    def first_selectable_plan_text(self) -> str:
        buttons = self.frame.locator(
            "button[lay-event='singleLaunch']:not(.operation-disabled)"
        )
        if buttons.count() == 0:
            body = self.frame.locator("body").inner_text(timeout=5000)
            raise LookupError(f"没有可发起的预算计划（非本部门/已引用？）：{body[:300]!r}")
        row = buttons.first.locator("xpath=ancestor::tr")
        return row.inner_text().strip()

    def click_single_launch(self):
        """点击第一条可发起的“单独发起”，返回新增采购申请的 layer iframe。"""
        button = self.frame.locator(
            "button[lay-event='singleLaunch']:not(.operation-disabled)"
        ).first
        button.click()
        return browser_helpers.get_frame(self.page, "procurementApply/edit.html")

    def fill_draft(self, edit_frame, data: dict) -> None:
        edit_frame.locator("[idname='projectName']").wait_for(state="visible", timeout=15000)
        edit_frame.fill("[idname='projectName']", data["project_name"])
        # Layui 会把原生 select 隐藏，直接 set value + 触发 change（与页面 getParamByIdName 一致）
        edit_frame.evaluate(
            """(value) => {
                const el = document.querySelector("[idname='projectAttribute']");
                if (!el) throw new Error('projectAttribute 不存在');
                el.value = value;
                el.dispatchEvent(new Event('change', { bubbles: true }));
                if (window.form && typeof window.form.render === 'function') {
                    window.form.render('select');
                }
            }""",
            data.get("project_attribute", "1"),
        )
        edit_frame.fill("[idname='purchaseContent']", data["purchase_content"])
        edit_frame.fill("[idname='applicationReason']", data["application_reason"])
        edit_frame.wait_for_timeout(300)

    def save_draft(self) -> None:
        """点击 layer 按钮“保存草稿”，等待弹窗关闭。"""
        save_button = self.page.locator(".layui-layer-btn a", has_text="保存草稿").last
        save_button.wait_for(state="visible", timeout=10000)
        save_button.click()
        # 等待编辑 iframe 消失（保存成功后关闭弹窗并刷新列表）
        for _ in range(60):
            if not any("procurementApply/edit.html" in f.url for f in self.page.frames):
                break
            self.page.wait_for_timeout(500)

    # ── 申请单管理 / 确认 ───────────────────────────────────
    def open_applications_tab(self) -> None:
        tab = self.frame.locator(".layui-tab-title li", has_text="申请单管理").first
        tab.wait_for(state="visible", timeout=10000)
        tab.click()
        wait_table_rows(self.frame)

    def find_application_row(self, project_name: str):
        return find_row_by_text(self.frame, project_name)

    def request_code_of(self, project_name: str) -> str:
        import re

        text = self.find_application_row(project_name).inner_text()
        match = re.search(r"[A-Z]{2,}-[A-Z0-9]+-CG\d+", text)
        if not match:
            raise LookupError(f"未能从行文本解析申请编号：{text[:200]!r}")
        return match.group()

    def confirm_application(self, project_name: str) -> str:
        """点击列表行“确认”，处理确认弹窗，返回操作方式（top/frame）。"""
        click_row_event(self.page, self.frame, project_name, "confirm")
        return browser_helpers.confirm_dialog(self.page, self.frame)
