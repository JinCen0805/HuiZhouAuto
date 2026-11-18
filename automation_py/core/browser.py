"""浏览器工厂与页面操作 helper：打开首页、changeView 开模块、iframe/弹窗定位。

本系统结构：
- 顶层 index.html（HP 或纪检监察平台）→ 左侧动态菜单 → 中央 layui tab + iframe；
- 弹窗两套：HCUI.popDialog.confirm/msg 弹在 top；layer.open 表单弹窗可能在当前 iframe。
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from core.config import Config

HP_INDEX = "/HospitalProcurement/index.html"
DISCIPLINE_INDEX = "/DisciplineInspection/index.html"
MENU_READY_SELECTOR = "#menu li"
PAGE_READY_TIMEOUT_MS = 20000


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


def new_context(browser, cookies: list[dict] | None = None, storage_state: str | dict | None = None,
                viewport: dict | None = None):
    ctx = browser.new_context(
        viewport=viewport or {"width": 1600, "height": 900},
        locale="zh-CN",
        storage_state=storage_state,
    )
    if cookies:
        ctx.add_cookies(cookies)
    return ctx


def open_hp(page, base_url: str, timeout_ms: int = 30000):
    """打开 HP 首页（或纪检监察平台跳转后的首页），等待动态菜单渲染。"""
    page.goto(base_url + HP_INDEX, wait_until="domcontentloaded", timeout=timeout_ms)
    # 纪检监察平台会由 /HospitalProcurement/view/disciplineInspection/index.html JS 跳转
    try:
        page.wait_for_url(re.compile(r".*(HospitalProcurement|DisciplineInspection)/index\.html.*"),
                          timeout=timeout_ms)
    except Exception:  # noqa: BLE001 - URL 正则兼容失败不阻断，继续等菜单
        pass
    page.wait_for_selector(MENU_READY_SELECTOR, timeout=timeout_ms)
    return page


def get_frame(page, url_pattern: str, timeout_ms: int = PAGE_READY_TIMEOUT_MS):
    """按 URL 子串等待并返回目标 iframe。"""
    deadline = time.time() + timeout_ms / 1000
    pattern = url_pattern.split("?")[0]
    last_error: Exception | None = None
    while time.time() < deadline:
        for frame in page.frames:
            if pattern in frame.url:
                try:
                    frame.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                return frame
        page.wait_for_timeout(200)
    raise TimeoutError(f"未找到 iframe：{url_pattern}；当前 frames="
                       f"{[f.url for f in page.frames]}") from last_error


def open_module(page, url: str, title: str = "", node_id: str = "", timeout_ms: int = PAGE_READY_TIMEOUT_MS):
    """通过顶层 changeView(title, url, nodeId) 打开业务模块，返回 iframe（Frame）。

    比菜单点击稳定：不依赖菜单展开状态；nodeId 可传任意唯一串（仅用于 tab 标识）。
    """
    node_id = node_id or ("smoke-" + re.sub(r"\W+", "-", url))
    page.evaluate(
        """([u, t, id]) => {
            if (typeof changeView !== 'function') throw new Error('changeView 不存在');
            changeView(t, u, id);
        }""",
        [url, title or url, node_id],
    )
    return get_frame(page, url, timeout_ms)


def confirm_dialog(page, frame=None, button_text: str = "确定", timeout_ms: int = 15000) -> str:
    """点击 Layui 确认弹窗的确定按钮；top 优先，frame 兜底。

    返回 'top' 或 'frame'（便于排查）。
    """
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        top_ok = page.locator(".layui-layer-dialog .layui-layer-btn0")
        if top_ok.count() > 0:
            top_ok.last.click()
            return "top"
        if frame is not None:
            frame_ok = frame.locator(".layui-layer-dialog .layui-layer-btn0")
            if frame_ok.count() > 0:
                frame_ok.last.click()
                return "frame"
        page.wait_for_timeout(200)
    raise TimeoutError(f"未出现确认弹窗（按钮文案：{button_text}）")


def wait_for_msg(page, frame=None, timeout_ms: int = 8000) -> str:
    """等待 float msg 并返回文本；没有则返回空串。"""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        loc = page.locator(".layui-layer-msg")
        if loc.count() > 0:
            return (loc.last.inner_text() or "").strip()
        if frame is not None:
            floc = frame.locator(".layui-layer-msg")
            if floc.count() > 0:
                return (floc.last.inner_text() or "").strip()
        page.wait_for_timeout(200)
    return ""
