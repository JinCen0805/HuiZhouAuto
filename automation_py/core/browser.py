"""浏览器工厂与页面操作基础（WP0 只提供最小能力，WP1 扩展 iframe/弹窗 helper）。"""
from __future__ import annotations

from pathlib import Path

from core.config import Config

HP_INDEX = "/HospitalProcurement/index.html"


def chromium_path(cfg: Config | None = None) -> str:
    cfg = cfg or Config.load()
    path = Path(cfg.chromium_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Chromium 不存在：{path}\n请安装或修改 HP_CHROMIUM 环境变量 / config.DEFAULT_CHROMIUM"
        )
    return str(path)


def launch(playwright, cfg: Config | None = None, headless: bool = True):
    """启动 Chromium，返回 Browser。"""
    return playwright.chromium.launch(
        executable_path=chromium_path(cfg),
        headless=headless,
    )


def new_context(browser, cookies: list[dict] | None = None, viewport: dict | None = None):
    ctx = browser.new_context(
        viewport=viewport or {"width": 1600, "height": 900},
        locale="zh-CN",
    )
    if cookies:
        ctx.add_cookies(cookies)
    return ctx


def open_hp(page, http_session, timeout_ms: int = 30000):
    """打开 HP 首页并等待动态菜单渲染。"""
    page.goto(http_session.base_url + HP_INDEX, wait_until="domcontentloaded",
              timeout=timeout_ms)
    page.wait_for_selector("#menu li", timeout=timeout_ms)
    return page
