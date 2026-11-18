"""冒烟测试夹具：启动一次 Chromium，按角色创建 BrowserSession（session 级复用）。"""
from __future__ import annotations

import pytest

from core import browser as browser_helpers
from core.config import Config
from core.session import BrowserSession

# 角色 → (账号, 平台, 角色关键字)
ROLE_SPECS = {
    "applicant": ("cbbm1", "采购交易系统", "承办部门经办"),
    "director": ("zhaoliu", "采购交易系统", "承办部门主任"),
    "supervisor": ("jjzr", "纪检监察平台", "纪检监察主任"),
    "auditor": ("sjyj", "纪检监察平台", "审计员"),
    "supplier": ("ybjcsgys1", "采购交易系统", "供应商"),
}


@pytest.fixture(scope="session")
def smoke_browser(playwright_instance, config):
    browser = browser_helpers.launch(playwright_instance, config, headless=True)
    yield browser
    browser.close()


@pytest.fixture(scope="session")
def smoke_sessions(smoke_browser, config):
    sessions: dict[str, BrowserSession] = {}
    for role, (username, platform, role_keyword) in ROLE_SPECS.items():
        session = BrowserSession(
            smoke_browser, config, username, platform, role_keyword=role_keyword,
            use_cache=True,
        )
        session.open()
        sessions[role] = session
    yield sessions
    for session in sessions.values():
        session.close()
