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
        browser_helpers.close_all_layers(self.page)
        self._close_stale_edit_layer()
        # 默认“发起采购申请”页签，等待可发起的预算计划按钮出现
        self.frame.locator("button[lay-event='singleLaunch']").first.wait_for(
            state="visible", timeout=20000
        )

    # ── 发起采购申请 ─────────────────────────────────────────
    def _selectable_buttons(self):
        return self.frame.locator(
            "button[lay-event='singleLaunch']:not(.operation-disabled):visible"
        )

    def selectable_plan_count(self) -> int:
        return self._selectable_buttons().count()

    def selectable_plan_entries(self) -> list[dict]:
        """返回当前可发起计划列表（索引 + 行文本），用于跳过不可用计划。"""
        entries = []
        buttons = self._selectable_buttons()
        for index in range(buttons.count()):
            try:
                row = buttons.nth(index).locator("xpath=ancestor::tr")
                text = row.inner_text(timeout=3000).strip()
            except Exception:  # noqa: BLE001
                text = ""
            entries.append({"index": index, "text": text})
        return entries

    def selectable_plan_text(self, index: int = 0) -> str:
        buttons = self._selectable_buttons()
        if buttons.count() == 0:
            body = self.frame.locator("body").inner_text(timeout=5000)
            raise LookupError(f"没有可发起的预算计划（非本部门/已引用？）：{body[:300]!r}")
        row = buttons.nth(index).locator("xpath=ancestor::tr")
        return row.inner_text().strip()

    def first_selectable_plan_text(self) -> str:
        return self.selectable_plan_text(0)

    def click_single_launch(self, index: int = 0):
        """点击第 index 条可发起的“单独发起”，返回新增采购申请的 layer iframe。"""
        button = self._selectable_buttons().nth(index)
        button.scroll_into_view_if_needed(timeout=5000)
        button.click(force=True, timeout=10000)
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

    def _edit_layer_open(self) -> bool:
        return any("procurementApply/edit.html" in f.url for f in self.page.frames)

    def _close_stale_edit_layer(self) -> None:
        """关闭可能残留/自动恢复的采购申请编辑弹窗（不影响新建流程）。"""
        if not self._edit_layer_open():
            return
        close_btn = self.page.locator(
            ".layui-layer:has(iframe[src*='procurementApply/edit.html']) .layui-layer-close"
        ).last
        if close_btn.count() > 0:
            try:
                close_btn.click(timeout=3000)
                self.page.wait_for_timeout(800)
            except Exception:  # noqa: BLE001 - 关闭失败则交给后续逻辑
                pass

    def _error_layer_text(self) -> str:
        """返回保存失败类提示弹窗文本（没有则空串）。"""
        layers = self.page.locator(".layui-layer")
        for i in range(layers.count()):
            try:
                text = (layers.nth(i).inner_text(timeout=1000) or "").strip()
            except Exception:  # noqa: BLE001
                continue
            if any(word in text for word in ("不存在", "不可引用", "失败", "错误", "不能", "请选择")):
                return text
        return ""

    def save_draft(self) -> bool:
        """点击“保存草稿”；成功返回 True，失败（弹窗提示/选中不合法）返回 False。"""
        save_button = self.page.locator(".layui-layer-btn a", has_text="保存草稿").last
        save_button.wait_for(state="visible", timeout=10000)
        save_button.click()
        for _ in range(40):  # 最多 20s
            if not self._edit_layer_open():
                return True
            error_text = self._error_layer_text()
            if error_text:
                print(f"[S01] 保存草稿被拒绝：{error_text[:120]!r}")
                self._close_all_layers()
                return False
            self.page.wait_for_timeout(500)
        body = ""
        for frame in self.page.frames:
            if "procurementApply/edit.html" in frame.url:
                try:
                    body = frame.locator("body").inner_text(timeout=3000)[:500]
                except Exception:  # noqa: BLE001
                    pass
        print(f"[S01] 保存草稿超时未关闭；弹窗文本：{body!r}")
        self._close_all_layers()
        return False

    def _close_all_layers(self) -> None:
        try:
            self.page.evaluate(
                """() => {
                    try { if (window.top && window.top.layer) window.top.layer.closeAll(); } catch (e) {}
                    try { if (window.layer) window.layer.closeAll(); } catch (e) {}
                }"""
            )
            self.page.wait_for_timeout(800)
        except Exception:  # noqa: BLE001
            pass
        self._close_stale_edit_layer()

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
