#!/usr/bin/env python
"""环境自检：本地全栈、网关、关键能力、账号、附件素材。

用法（在 automation_py 目录）：
    python scripts/env_check.py
    python scripts/env_check.py --strict   # WARN 也视为失败

退出码：0 = 无 FAIL；1 = 存在 FAIL（或 --strict 下的 WARN）。
"""
from __future__ import annotations

import argparse
import socket
import sys
import time
from pathlib import Path

# 中文输出（Windows 控制台默认 GBK，这里统一 UTF-8）
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

# 允许直接运行：python scripts/env_check.py
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import requests  # noqa: E402

from core.config import Config, FLOW_CONFIG_PATH  # noqa: E402
from core.session import login_http  # noqa: E402

CFG = Config.load()
RESULTS: list[dict] = []
started_global = time.time()

# 账号检查：(账号, 平台, 期望角色关键字)
CORE_ACCOUNTS = [
    ("cbbm1", "采购交易系统", "承办部门经办"),
    ("jjzr", "纪检监察平台", "纪检监察主任"),
    ("ybjcsgys1", "采购交易系统", "供应商"),
]
EXTRA_ACCOUNTS = [
    ("zhaoliu", "采购交易系统", "承办部门主任"),
    ("libai", "采购交易系统", "分管院领导"),
    ("bailu", "采购交易系统", "采购执行部门主任"),
    ("baiqi", "采购交易系统", "医院办公室主任"),
    ("fgld", "采购交易系统", "分管领导"),
    ("fgyld", "采购交易系统", "分管院领导"),
    ("sjyj", "纪检监察平台", "审计员"),
    ("sjbzr", "纪检监察平台", "审计部主任"),
    ("ybjcsgys2", "采购交易系统", "供应商"),
    ("ybjcsgys3", "采购交易系统", "供应商"),
    ("cy-zj1", "采购交易系统", "专家"),
]


def record(name: str, status: str, detail: str = "", hint: str = "") -> None:
    RESULTS.append({"name": name, "status": status, "detail": detail, "hint": hint})
    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]"}[status]
    line = f"{icon} {name}"
    if detail:
        line += f"  ({detail})"
    print(line)
    if status == "FAIL" and hint:
        print(f"       >> 修复建议：{hint}")


def run(name: str, func, required: bool = True, hint: str = "") -> None:
    try:
        detail = func()
        record(name, "PASS", str(detail) if detail else "")
    except Exception as exc:  # noqa: BLE001 - 自检需要捕获所有异常
        status = "FAIL" if required else "WARN"
        record(name, status, str(exc).splitlines()[0][:200], hint)


# ── A. 基础环境 ─────────────────────────────────────────────
def check_python() -> str:
    if sys.version_info < (3, 10):
        raise RuntimeError(f"Python 版本过低：{sys.version.split()[0]}")
    return sys.version.split()[0]


def check_imports() -> str:
    import pytest
    import requests  # noqa: F401
    from playwright.sync_api import sync_playwright  # noqa: F401

    return f"pytest {pytest.__version__}"


def check_chromium() -> str:
    from core.browser import chromium_path

    path = Path(chromium_path(CFG))
    if path.stat().st_size < 1024 * 1024:
        raise RuntimeError(f"Chromium 文件异常：{path}")
    return f"{path.name} ({path.stat().st_size // 1024 // 1024} MB)"


def check_playwright_launch() -> str:
    from playwright.sync_api import sync_playwright

    from core.browser import launch, new_context

    with sync_playwright() as pw:
        browser = launch(pw, CFG, headless=True)
        try:
            ctx = new_context(browser)
            page = ctx.new_page()
            page.goto(CFG.base_url + "/HospitalProcurement/index.html",
                      wait_until="domcontentloaded", timeout=30000)
            title = page.title()
            if not title:
                raise RuntimeError("页面标题为空")
            return f"title={title!r}"
        finally:
            browser.close()


# ── B. 服务健康 ─────────────────────────────────────────────
def http_ok(path: str, timeout: int = 8) -> str:
    url = path if path.startswith("http") else CFG.base_url + path
    resp = requests.get(url, timeout=timeout, allow_redirects=False)
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code} {url}")
    return f"HTTP {resp.status_code}"


def check_gateway_route() -> str:
    """新版页面调用 /hospital-procurement/api/...；404 说明本地网关缺路由。"""
    resp = requests.get(CFG.base_url + "/hospital-procurement/api/plan-management/reserve-library/years",
                        timeout=8, allow_redirects=False)
    if resp.status_code == 404:
        raise RuntimeError("网关 404：/hospital-procurement/ 路由缺失（新版页面会报数据接口异常）")
    return f"HTTP {resp.status_code}"


def check_mock_enabled() -> str:
    resp = requests.get(CFG.base_url + "/professor/expertExtract/mock/enabled", timeout=8)
    body = resp.json()
    enabled = ((body or {}).get("data") or {}).get("enabled")
    if enabled is not True:
        raise RuntimeError(f"professor mock 未开启：{body}")
    return "enabled=true"


def check_onlyoffice() -> str:
    host, port = "127.0.0.1", 18099
    with socket.create_connection((host, port), timeout=3):
        return f"{host}:{port} 可连接"


def check_draw_mq_bridge() -> str:
    """检查本地抽取建项 MQ 桥接：professor 是否在 HP vhost 上消费建项队列。"""
    import subprocess

    result = subprocess.run(
        ["docker", "exec", "hospital-local-stack-rabbitmq-1",
         "rabbitmqctl", "list_queues", "-p", "/local-hospital-procurement", "name", "consumers"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"RabbitMQ 查询失败：{result.stderr[:200]}")
    for line in result.stdout.splitlines():
        if "professor.draw.create.queue" in line:
            parts = line.split()
            if parts and int(parts[-1]) >= 1:
                return "professor.draw.create.queue 有消费者"
            raise RuntimeError("professor 建项队列无消费者")
    raise RuntimeError("未找到 professor.draw.create.queue")


# ── C. 账号与关键接口 ───────────────────────────────────────
def check_account(username: str, platform: str, role_keyword: str) -> str:
    password = CFG.password(username)
    session = login_http(username, password, platform, CFG.base_url, role_keyword=role_keyword)
    if role_keyword not in (session.role or ""):
        raise RuntimeError(f"角色不符：期望包含 {role_keyword!r}，实际 {session.role!r}")
    menu = session.menu_json()
    items = menu.get("content") if isinstance(menu.get("content"), list) else []
    if not items:
        raise RuntimeError(f"菜单为空：{str(menu)[:200]}")
    return f"role={session.role} menus={len(items)}"


def check_jjjc_auth() -> str:
    password = CFG.password("jjzr")
    session = login_http("jjzr", password, "纪检监察平台", CFG.base_url,
                         role_keyword="纪检监察主任")
    resp = session.get("/jjjc/supervise/canManageAssignment", headers={"Accept": "application/json"})
    if resp.status_code == 401:
        raise RuntimeError("纪检接口 401：本地 Redis DB 不一致（registers=9 / discipline=7）")
    body = resp.json() if resp.text.startswith("{") else {}
    if not body.get("success"):
        raise RuntimeError(f"纪检接口异常：{resp.status_code} {resp.text[:200]}")
    return f"canManage={body.get('canManage')}"


def check_reserve_api() -> str:
    password = CFG.password("cbbm1")
    session = login_http("cbbm1", password, "采购交易系统", CFG.base_url,
                         role_keyword="承办部门经办")
    resp = session.get("/hospital-procurement/api/plan-management/reserve-library/years",
                       headers={"Accept": "application/json"})
    if resp.status_code != 200:
        raise RuntimeError(f"预算计划接口异常：HTTP {resp.status_code} {resp.text[:160]}")
    body = resp.json()
    data = body.get("data")
    if body.get("code") not in (0, "0"):
        raise RuntimeError(f"预算计划接口业务失败：{str(body)[:200]}")
    count = len(data) if isinstance(data, list) else "?"
    return f"years={count}"


def check_fixtures() -> str:
    files_dir = PACKAGE_ROOT / "fixtures" / "files"
    pdf = files_dir / "wjc测试文件.pdf"
    docx = files_dir / "wjc测试文件.docx"
    for path in (pdf, docx):
        if not path.exists():
            raise RuntimeError(f"缺少附件素材：{path}")
    if not pdf.read_bytes()[:4] == b"%PDF":
        raise RuntimeError("PDF 文件头异常")
    if not docx.read_bytes()[:2] == b"PK":
        raise RuntimeError("DOCX 文件头异常")
    return f"{pdf.stat().st_size}B / {docx.stat().st_size}B"


def check_flow_config() -> str:
    if not FLOW_CONFIG_PATH.exists():
        return "未创建（WP0 允许，WP2 前补齐）"
    import json

    data = json.loads(FLOW_CONFIG_PATH.read_text(encoding="utf-8"))
    return f"keys={len(data)}"


def check_reports_writable() -> str:
    reports = PACKAGE_ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    probe = reports / ".write_probe"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    return str(reports)


def run_online_checks() -> int:
    """线上环境只读自检：入口、登录、关键接口、专家 mock、OnlyOffice。"""
    from core.env_profile import accounts as env_accounts

    print("\n[A] 基础环境")
    run("Python 版本", check_python)
    run("依赖导入", check_imports)
    run("Chromium 存在", check_chromium)
    run("Playwright 启动浏览器", check_playwright_launch)

    print("\n[B] 线上入口与关键接口")
    run("线上首页", lambda: http_ok("/HospitalProcurement/index.html"))
    run("登录页", lambda: http_ok("/Register/public/newLogin/user_login_2.html"))
    run("动态菜单服务", lambda: http_ok("/nodeJs/menu_Json"))
    run("专家 mock 已启用", check_mock_enabled)
    run("采购执行服务", lambda: http_ok("/ProcurementExecution/purchase/purchaseProject/getPage?current=1&size=1"))
    onlyoffice_url = CFG.env("HP_ONLYOFFICE_HEALTH_URL", "http://172.16.29.214:8099/healthcheck")
    run("OnlyOffice 健康检查", lambda: http_ok(onlyoffice_url), required=False,
        hint="确认线上 OnlyOffice 地址可从自动化机器访问")

    print("\n[C] 账号登录（线上测试账号，只读）")
    seen = set()
    for _role, (username, platform, role_keyword) in env_accounts().items():
        if username in seen:
            continue
        seen.add(username)
        if not (CFG.env("HP_PASSWORD_" + username.upper().replace("-", "_")) or CFG.env("HP_PASS")):
            record(f"账号 {username}", "WARN", "未配置密码，跳过")
            continue
        run(f"账号 {username}", lambda u=username, p=platform, r=role_keyword: check_account(u, p, r),
            required=False)

    print("\n[D] 素材与目录")
    run("附件素材", check_fixtures)
    run("业务参数配置", check_flow_config, required=False)
    run("报告目录可写", check_reports_writable)

    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    warned = sum(1 for r in RESULTS if r["status"] == "WARN")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    elapsed = time.time() - started_global
    print("\n" + "=" * 78)
    print(f"结果：PASS {passed} / WARN {warned} / FAIL {failed}   耗时 {elapsed:.1f}s")
    print("=" * 78)
    if failed:
        print("存在失败项，请按上面的修复建议处理。")
        return 1
    print("线上环境自检通过（只读）。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="WARN 也视为失败")
    args = parser.parse_args()

    if not CFG.is_local:
        return run_online_checks()

    started = time.time()
    print("=" * 78)
    print("采购前置流程自动化 · 环境自检")
    print(f"base_url = {CFG.base_url}")
    print(f"package  = {PACKAGE_ROOT}")
    print("=" * 78)

    print("\n[A] 基础环境")
    run("Python 版本", check_python, hint="安装 Python 3.12+")
    run("依赖导入", check_imports, hint="pip install -r requirements.txt")
    run("Chromium 存在", check_chromium, hint="安装 Chromium 或设置 HP_CHROMIUM")
    run("Playwright 启动浏览器", check_playwright_launch,
        hint="检查 Chromium 路径与本地前端是否启动")

    print("\n[B] 服务健康")
    for name, path in [
        ("前端 HP 首页", "/HospitalProcurement/index.html"),
        ("HP 服务(17825)", "http://127.0.0.1:17825/health"),
        ("Register 登录页", "/Register/public/newLogin/user_login_2.html"),
        ("纪检监察服务", "/jjjc/health"),
        ("审批服务", "/EbiddingBusinessApproval/health"),
        ("专家库服务", "/professor/health"),
        ("动态菜单服务", "/nodeJs/health"),
        ("模板服务", "/TemplateService/health"),
        ("文件服务", "/ebiddingFile/health"),
        ("采购执行服务", "/ProcurementExecution/health"),
        ("计划服务", "/PlanManagement/health"),
        ("运营平台", "/operation_platform/health"),
        ("公共门户", "/PublicServer/health"),
    ]:
        run(name, lambda p=path: http_ok(p), hint="运行 start-local-project.cmd 启动本地全栈")
    run("新版 API 网关路由", check_gateway_route,
        hint="在 openresty/local-dev/nginx.conf 增加 /hospital-procurement/ 反代")
    run("专家 mock 已启用", check_mock_enabled,
        hint="professor local 配置 expert.extract.mock-callback.enabled=true")

    print("\n[C] 账号与关键接口")
    for username, platform, role_keyword in CORE_ACCOUNTS:
        run(f"账号 {username}", lambda u=username, p=platform, r=role_keyword: check_account(u, p, r),
            hint=f"设置环境变量 HP_PASSWORD_{username.upper().replace('-', '_')}")
    for username, platform, role_keyword in EXTRA_ACCOUNTS:
        if not (CFG.env("HP_PASSWORD_" + username.upper().replace("-", "_")) or CFG.env("HP_PASS")):
            record(f"账号 {username}", "WARN", "未配置密码，跳过")
        else:
            run(f"账号 {username}", lambda u=username, p=platform, r=role_keyword: check_account(u, p, r),
                required=False)
    run("纪检接口鉴权(Redis 对齐)", check_jjjc_auth,
        hint="同步 jjzr 登录 key 到 Redis DB7，或把 discipline 的 SPRING_REDIS_DATABASE 改为 9")
    run("预算计划接口", check_reserve_api,
        hint="确认网关路由与 cbbm1 账号权限")

    print("\n[D] 素材与运行目录")
    run("附件素材", check_fixtures, hint="把 wjc测试文件.pdf/.docx 放入 fixtures/files/")
    run("业务参数配置", check_flow_config, required=False)
    run("报告目录可写", check_reports_writable)

    print("\n[E] 可选环境（后续阶段需要）")
    run("OnlyOffice(18099)", check_onlyoffice, required=False,
        hint="WP6 前需启动 OnlyOffice 容器（采购需求书/审计报告在线编辑）")
    run("抽取建项 MQ 桥接", check_draw_mq_bridge, required=False,
        hint="按 WP5 方案 A 修改 local-stack（professor vhost/listener）并重启 professor；"
             "HP relay 由 scripts/local_draw_bridge.py 本地桥接")

    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    warned = sum(1 for r in RESULTS if r["status"] == "WARN")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    elapsed = time.time() - started
    print("\n" + "=" * 78)
    print(f"结果：PASS {passed} / WARN {warned} / FAIL {failed}   耗时 {elapsed:.1f}s")
    print("=" * 78)
    if failed:
        print("存在失败项，请按上面的修复建议处理。")
        return 1
    if args.strict and warned:
        print("--strict 模式：存在 WARN，视为失败。")
        return 1
    print("环境自检通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
