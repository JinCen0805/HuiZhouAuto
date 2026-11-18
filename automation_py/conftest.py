"""pytest 全局配置：路径注入、可选参数、Playwright 实例 fixture。

说明：
- 本项目是多账号、有状态流程，**不使用** pytest-playwright 的 page/browser fixture；
  只借用 `playwright_instance` 拿到 Playwright 实例，browser/context/page 由 core 层自管。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import Config  # noqa: E402


def pytest_addoption(parser) -> None:
    parser.addoption("--run-id", action="store", default=None,
                     help="运行标记（数据前缀/报告目录），不传则自动生成")
    parser.addoption("--env-file", action="store", default=None,
                     help="指定 .env.local 路径")


@pytest.fixture(scope="session")
def run_id(request) -> str:
    from core.reporter import new_run_id

    return request.config.getoption("--run-id") or new_run_id()


@pytest.fixture(scope="session")
def config() -> Config:
    return Config.load()


@pytest.fixture(scope="session")
def playwright_instance():
    """Playwright 实例（session 级，只启动一次）。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        yield pw
