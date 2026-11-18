"""主链测试夹具：按角色创建 BrowserSession（session 级复用）。"""
from __future__ import annotations

import pytest

from core import browser as browser_helpers
from core.session import BrowserSession

ROLE_SPECS = {
    "applicant": ("cbbm1", "采购交易系统", "承办部门经办"),
    "supervisor": ("jjzr", "纪检监察平台", "纪检监察主任"),
    "director": ("zhaoliu", "采购交易系统", "承办部门主任"),
}


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
