#!/usr/bin/env python
"""线上只读冒烟（阶段0）：不创建/修改任何业务数据。

用法（开发/线上环境，只读）：
    $env:HP_ENV='online'
    $env:HP_BASE_URL='http://172.16.29.215'
    python scripts/online_smoke.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import requests  # noqa: E402

from core import browser as browser_helpers  # noqa: E402
from core.config import Config  # noqa: E402
from core.env_profile import accounts  # noqa: E402
from core.reporter import Reporter, new_run_id  # noqa: E402
from core.session import BrowserSession, HttpSession  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

CFG = Config.load()
HEADERS = {"Accept": "application/json, text/javascript, */*; q=0.01"}

MODULES = [
    ("采购申请管理", "/HospitalProcurement/view/procurementApply/list.html"),
    ("分包管理", "/HospitalProcurement/view/packageManagement/index.html"),
    ("调研项目管理", "/HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyProject/list.html"),
    ("调研结果管理", "/HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyResult/list.html"),
    ("调研论证管理", "/HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyArgument/list.html"),
    ("采购需求在线编制", "/HospitalProcurement/view/procurementRequirement/index.html"),
    ("审计管理", "/HospitalProcurement/view/auditManagement/index.html"),
    ("采购需求审查管理", "/HospitalProcurement/view/procurementRequirementReview/index.html"),
    ("采购方式分配", "/HospitalProcurement/view/procurementMethodConfirm/index.html"),
    ("采购执行申请管理", "/HospitalProcurement/view/executionApply/list.html"),
]


def check_http(name: str, path: str, reporter: Reporter) -> None:
    started = time.time()
    last_error = ""
    for attempt in range(3):
        try:
            url = path if path.startswith("http") else CFG.base_url + path
            resp = requests.get(url, timeout=15, allow_redirects=True)
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}")
            reporter.stage(name, path, "success", int((time.time() - started) * 1000))
            print(f"[PASS] {name}  HTTP {resp.status_code}")
            return
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            time.sleep(2)
    reporter.stage(name, path, "failed", int((time.time() - started) * 1000), error=last_error)
    print(f"[FAIL] {name}  {last_error}")


def check_login(role: str, spec: tuple[str, str, str], reporter: Reporter) -> HttpSession | None:
    username, platform, keyword = spec
    started = time.time()
    try:
        password = CFG.password(username)
        session = HttpSession(base_url=CFG.base_url)
        session.login(username, password)
        redirect = session.goto_index(platform, keyword)
        session.get(redirect)
        if keyword not in (session.role or ""):
            raise RuntimeError(f"角色不符：期望 {keyword!r}，实际 {session.role!r}")
        menu = session.menu_json()
        items = menu.get("content") if isinstance(menu.get("content"), list) else []
        if not items:
            raise RuntimeError("菜单为空")
        reporter.stage(f"登录-{role}", f"{username}/{platform}", "success",
                       int((time.time() - started) * 1000), role=session.role, menus=len(items))
        print(f"[PASS] 登录 {username}（{platform}）role={session.role} menus={len(items)}")
        return session
    except Exception as exc:  # noqa: BLE001
        reporter.stage(f"登录-{role}", f"{username}/{platform}", "failed",
                       int((time.time() - started) * 1000), error=str(exc))
        print(f"[FAIL] 登录 {username}/{platform}: {exc}")
        return None


def check_api(name: str, session: HttpSession, path: str, reporter: Reporter,
              success_key: str = "success") -> None:
    started = time.time()
    last_error = ""
    for attempt in range(3):
        try:
            resp = session.api(path, headers=HEADERS)
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:120]}")
            body = resp.json() or {}
            if not body.get(success_key) and success_key in body:
                raise RuntimeError(f"接口失败：{str(body)[:200]}")
            reporter.stage(name, path, "success", int((time.time() - started) * 1000))
            print(f"[PASS] {name}")
            return
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            time.sleep(2)
    reporter.stage(name, path, "failed", int((time.time() - started) * 1000), error=last_error)
    print(f"[FAIL] {name}: {last_error}")


def main() -> int:
    if CFG.is_local:
        print("当前是本地环境；本脚本用于线上只读冒烟。")
        return 2
    run_id = new_run_id()
    reporter = Reporter(f"online-smoke-{run_id}")
    print(f"线上只读冒烟：{CFG.base_url}  runId={run_id}")

    print("\n[A] 入口与基础服务")
    check_http("线上首页", "/HospitalProcurement/index.html", reporter)
    check_http("登录页", "/Register/public/newLogin/user_login_2.html", reporter)
    check_http("动态菜单服务", "/nodeJs/menu_Json", reporter)
    mock_page = CFG.env("HP_PROFESSOR_MOCK_PAGE",
                        f"http://{CFG.host}:7817/expertExtract/mock/index.html")
    check_http("专家 mock 页面", mock_page, reporter)
    check_http("专家 mock 接口", "/professor/expertExtract/mock/enabled", reporter)
    check_http("专家 mock 项目列表", "/professor/expertExtract/mock/projects?page=1&pageSize=3", reporter)
    check_http("OnlyOffice", CFG.env("HP_ONLYOFFICE_HEALTH_URL", "http://172.16.29.214:8099/healthcheck"),
               reporter)

    print("\n[B] 账号与角色（只读登录）")
    sessions: dict[str, HttpSession] = {}
    for role, spec in accounts().items():
        session = check_login(role, spec, reporter)
        if session is not None:
            sessions[role] = session
        time.sleep(1.0)

    print("\n[C] 关键只读接口")
    if "applicant" in sessions:
        applicant = sessions["applicant"]
        check_api("用户信息", applicant, "/HospitalProcurement/basicinfo/userinfo/getUserBasicInfo", reporter)
        try:
            info = (applicant.api("/HospitalProcurement/basicinfo/userinfo/getUserBasicInfo",
                                  headers=HEADERS).json() or {}).get("data") or {}
        except Exception:  # noqa: BLE001 - 线上偶发非 JSON 响应
            info = {}
        dept = info.get("organizationId") or ""
        if dept:
            check_api("采购申请列表", applicant,
                      f"/HospitalProcurement/hospitalPurchaseRequest/page?current=1&size=5&departmentId={dept}",
                      reporter)
        else:
            reporter.stage("采购申请列表", "", "failed", error="用户信息缺少 organizationId")
            print("[FAIL] 采购申请列表：用户信息缺少 organizationId")
        check_api("审计列表", applicant, "/HospitalProcurement/hospitalPurchaseAudit/page?current=1&size=5", reporter)
        check_api("需求审查列表", applicant,
                  "/HospitalProcurement/hospitalPurchaseDemandReview/page?current=1&size=5", reporter)
        check_api("PE 执行项目列表", applicant,
                  "/ProcurementExecution/purchase/purchaseProject/getPage?current=1&size=5", reporter)
        check_api("PE 经办人候选", applicant,
                  "/ProcurementExecution/purchase/purchaseProject/purchaseContactList", reporter)
    if "auditor" in sessions:
        check_api("纪检审计列表", sessions["auditor"],
                  "/jjjc/purchaseAudit/page?auditStatus=1&pageNum=1&pageSize=5", reporter)

    print("\n[D] 线上页面加载（只读，不点击保存/提交）")
    if "applicant" in sessions or "director" in sessions:
        role = "applicant" if "applicant" in sessions else "director"
        username, platform, keyword = accounts()[role]
        with sync_playwright() as pw:
            browser = browser_helpers.launch(pw, CFG, headless=True)
            try:
                bs = BrowserSession(browser, CFG, username, platform, role_keyword=keyword, use_cache=False)
                bs.open()
                print(f"[PASS] 浏览器登录 {username}（{bs.page.url}）")
                for name, url in MODULES:
                    started = time.time()
                    try:
                        frame = None
                        text = ""
                        for page_attempt in range(2):
                            frame = bs.open_module(CFG.base_url + url, name)
                            frame.wait_for_timeout(1800)
                            try:
                                text = frame.locator("body").inner_text(timeout=15000)
                                break
                            except Exception:
                                if page_attempt == 1:
                                    raise
                                time.sleep(2)
                        if not text.strip() or "404" in text[:100]:
                            raise RuntimeError(f"页面内容异常：{text[:120]!r}")
                        reporter.stage(f"页面-{name}", url, "success",
                                       int((time.time() - started) * 1000), text=head_text(text))
                        print(f"[PASS] 页面 {name}")
                    except Exception as exc:  # noqa: BLE001
                        reporter.stage(f"页面-{name}", url, "failed",
                                       int((time.time() - started) * 1000), error=str(exc))
                        print(f"[FAIL] 页面 {name}: {exc}")
            finally:
                browser.close()

    passed = sum(1 for s in reporter.stages if s["status"] == "success")
    failed = sum(1 for s in reporter.stages if s["status"] == "failed")
    result = "success" if failed == 0 else "failed"
    path = reporter.finish(result)
    print(f"\n结果：PASS {passed} / FAIL {failed}")
    print(f"报告：{path} / {path.with_suffix('.html')}")
    return 0 if failed == 0 else 1


def head_text(text: str, limit: int = 80) -> str:
    return " ".join(text.split())[:limit]


if __name__ == "__main__":
    raise SystemExit(main())
