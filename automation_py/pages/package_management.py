"""分包管理页（S05）：分包 → 新增子包 → 保存 → 确认锁定。"""
from __future__ import annotations

from core import browser as browser_helpers
from pages.common import READY_TIMEOUT_MS, click_row_event, wait_table_rows

MODULE_URL = "/HospitalProcurement/view/packageManagement/index.html"
MENU_ID = "0000006000002"
EDITOR_URL_PATTERN = "packageManagement/editor/index.html"


class PackageManagementPage:
    def __init__(self, session):
        self.session = session
        self.page = session.page
        self.frame = session.open_module(MODULE_URL, "分包管理", MENU_ID)
        wait_table_rows(self.frame)

    def search(self, request_name: str) -> None:
        self.frame.fill("[idname='requestName']", request_name)
        self.frame.click("#packageSearchBtn")
        self.frame.wait_for_timeout(1500)
        wait_table_rows(self.frame)

    def open_editor(self, request_code: str):
        """点击行“分包”，返回分包编辑 iframe。"""
        click_row_event(self.page, self.frame, request_code, "edit")
        return browser_helpers.get_frame(self.page, EDITOR_URL_PATTERN)

    def add_subpackage(self, editor_frame, subpackage_name: str) -> None:
        """新增子包。名称由调用方按“申请单名称-子包1/2/3”传入。"""
        add_button = editor_frame.locator("button[data-action='addPackage']").first
        add_button.wait_for(state="visible", timeout=15000)
        add_button.click()
        editor_frame.locator("#dialogPackageName").wait_for(state="visible", timeout=10000)
        editor_frame.fill("#dialogPackageName", subpackage_name)
        # 勾选第一个未分配的预算计划
        checkboxes = editor_frame.locator(".package-item-select:not([disabled])")
        if checkboxes.count() == 0:
            raise LookupError("新增子包弹窗中没有可选择的预算计划")
        checkboxes.first.check(force=True)
        editor_frame.wait_for_timeout(300)
        editor_frame.locator(".layui-layer-btn a", has_text="保存").last.click()
        editor_frame.wait_for_timeout(2500)

    def editor_contains(self, editor_frame, text: str) -> bool:
        try:
            editor_frame.locator("body", has_text=text).wait_for(timeout=5000)
            return True
        except Exception:  # noqa: BLE001
            return False

    def close_editor(self) -> None:
        button = self.page.locator(".layui-layer-btn a", has_text="关闭")
        if button.count() > 0:
            button.last.click()
        else:
            # 编辑页内的关闭按钮
            try:
                editor = browser_helpers.get_frame(self.page, EDITOR_URL_PATTERN, timeout_ms=3000)
                editor.locator("#closeBtn").click()
            except Exception:  # noqa: BLE001
                pass
        self.page.wait_for_timeout(1500)

    def confirm_in_editor(self, editor_frame, timeout_ms: int = 20000) -> str:
        """在编辑器底部点击“确认”锁定分包方案，并处理确认弹窗。

        2026-11-27 起分包列表行不再提供“确认”按钮（f0a6274f），确认入口只剩编辑器
        底部 #confirmBtn；该按钮在旧版前端同样存在，因此本地/线上通用。
        返回确认弹窗出现的位置（'top' / 'frame'），便于排查。
        """
        button = editor_frame.locator("#confirmBtn")
        button.wait_for(state="visible", timeout=READY_TIMEOUT_MS)
        try:
            editor_frame.locator("#confirmBtn:not(.visual-disabled)").first.wait_for(
                state="visible", timeout=timeout_ms)
        except Exception as exc:  # noqa: BLE001 - 超时后给出页面提示的原因
            reason = button.get_attribute("title") or "未知原因"
            raise LookupError(f"编辑器“确认”按钮不可用：{reason}") from exc
        button.click()
        where = browser_helpers.confirm_dialog(self.page, editor_frame)
        try:
            editor_frame.locator("#packageStatus", has_text="已确认分包").wait_for(
                timeout=timeout_ms)
        except Exception as exc:  # noqa: BLE001
            msg = browser_helpers.wait_for_msg(self.page, editor_frame, timeout_ms=1500)
            raise AssertionError(
                f"点击确认后编辑器未变为“已确认分包”：{msg or '无提示信息'}") from exc
        return where
