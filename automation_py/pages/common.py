"""通用表格/弹窗辅助：行定位、行内按钮点击。"""
from __future__ import annotations

import time

from core.browser import confirm_dialog  # noqa: F401  (re-export 便于页面类使用)

READY_TIMEOUT_MS = 20000
VISIBLE_VIEW = ".layui-table-view:visible"


def wait_table_rows(frame, timeout_ms: int = READY_TIMEOUT_MS) -> None:
    """等待“可见的”表格至少出现一行数据（页签切换后旧表格仍隐藏，不能只看 DOM 存在）。"""
    frame.wait_for_function(
        """() => Array.from(document.querySelectorAll('.layui-table-view'))
                 .some(t => t.offsetParent !== null && t.querySelector('tbody tr'))""",
        timeout=timeout_ms,
    )


def find_row_by_text(frame, text: str, timeout_ms: int = READY_TIMEOUT_MS):
    """按行文本查找可见表格行（返回 Locator，多匹配取第一个）。"""
    deadline = time.time() + timeout_ms / 1000
    rows = frame.locator(f"{VISIBLE_VIEW} tr", has_text=text)
    while time.time() < deadline:
        if rows.count() > 0:
            return rows.first
        frame.wait_for_timeout(200)
    body = frame.locator("body").inner_text(timeout=5000)
    raise LookupError(f"未找到包含 {text!r} 的表格行；页面文本：{body[:300]!r}")


def click_row_event(page, frame, row_text: str, event: str) -> None:
    """点击某行内 `button[lay-event=event]`；优先点固定列中的可见按钮。"""
    selector = f"button[lay-event='{event}']"
    fixed_button = frame.locator(
        f"{VISIBLE_VIEW} .layui-table-fixed tr", has_text=row_text
    ).locator(selector)
    if fixed_button.count() > 0:
        fixed_button.first.click(force=True)
        return
    row = find_row_by_text(frame, row_text)
    button = row.locator(selector)
    if button.count() > 0:
        button.first.click(force=True)
        return
    raise LookupError(f"行 {row_text!r} 中未找到按钮 lay-event={event!r}")


def click_button_text(frame, text: str, timeout_ms: int = READY_TIMEOUT_MS) -> None:
    """按按钮文本点击（精确匹配优先）。"""
    locator = frame.locator("button", has_text=text)
    locator.first.wait_for(state="visible", timeout=timeout_ms)
    locator.first.click()


def page_has_text(frame, text: str, timeout_ms: int = 5000) -> bool:
    try:
        frame.locator("body", has_text=text).wait_for(timeout=timeout_ms)
        return True
    except Exception:  # noqa: BLE001
        return False
