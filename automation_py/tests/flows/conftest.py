"""主链测试夹具：按角色创建 BrowserSession（session 级复用）。"""
from __future__ import annotations

import pytest

from core import browser as browser_helpers
from core.session import BrowserSession

ROLE_SPECS = {
    "applicant": ("cbbm1", "采购交易系统", "承办部门经办"),
    "supervisor": ("jjzr", "纪检监察平台", "纪检监察主任"),
    "director": ("zhaoliu", "采购交易系统", "承办部门主任"),
    "supplier1": ("ybjcsgys1", "采购交易系统", "供应商"),
    "supplier2": ("ybjcsgys2", "采购交易系统", "供应商"),
    "supplier3": ("ybjcsgys3", "采购交易系统", "供应商"),
}

SUPPLIER_ROLES = ("supplier1", "supplier2", "supplier3")


@pytest.fixture(scope="session")
def flow_browser(playwright_instance, config):
    browser = browser_helpers.launch(playwright_instance, config, headless=True)
    yield browser
    browser.close()


@pytest.fixture(scope="session")
def flow_sessions(flow_browser, config):
    sessions = {}
    for role, (username, platform, role_keyword) in ROLE_SPECS.items():
        session = BrowserSession(
            flow_browser, config, username, platform,
            role_keyword=role_keyword, use_cache=True,
        )
        session.open()
        sessions[role] = session
    yield sessions
    for session in sessions.values():
        session.close()


@pytest.fixture(autouse=True)
def _reset_ui_between_tests(flow_sessions):
    """用例之间清理遗留弹窗（HCUI/layer），避免上一用例的弹窗遮挡下一用例。"""
    yield
    for session in flow_sessions.values():
        try:
            page = session.page
            if page is None:
                continue
            page.evaluate(
                """() => {
                    try { if (window.top && window.top.layer) window.top.layer.closeAll(); } catch (e) {}
                    try { if (window.layer) window.layer.closeAll(); } catch (e) {}
                }"""
            )
            page.wait_for_timeout(300)
        except Exception:  # noqa: BLE001 - 清理失败不影响主流程
            pass
