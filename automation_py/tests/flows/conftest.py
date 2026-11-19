"""主链测试夹具：按角色创建 BrowserSession（session 级复用）。"""
from __future__ import annotations

import pytest

from core import browser as browser_helpers
from core.session import BrowserSession

from core.env_profile import accounts as _env_accounts

ROLE_SPECS = _env_accounts()

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


def pytest_collection_modifyitems(config, items):
    """线上环境未显式允许写操作时，跳过所有 flows 业务用例，避免污染真实数据。"""
    import os
    from core.config import Config

    cfg = Config.load()
    if cfg.is_local or os.environ.get("HP_ALLOW_ONLINE_WRITES") == "1":
        return
    import pytest

    skip = pytest.mark.skip(reason="线上环境默认禁止写业务数据；如确需执行请设置 HP_ALLOW_ONLINE_WRITES=1")
    for item in items:
        item.add_marker(skip)
