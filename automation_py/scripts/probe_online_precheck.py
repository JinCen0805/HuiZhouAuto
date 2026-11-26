#!/usr/bin/env python
"""线上 215 全链前只读预检（不创建/修改任何业务数据）。

用法（在 automation_py 目录）：
    $env:HP_ENV='online'; $env:HP_BASE_URL='http://172.16.29.215'
    python scripts/probe_online_precheck.py --plan-count 3 \
        --name 项目名1 --name 项目名2 ... --name 项目名5

检查项：
1. 采购执行服务（PE）鉴权后的关键接口是否可用（env_check 的匿名 GET 404 复核）；
2. 每个采购申请名字是否已被占用（同名会导致申请单管理无法区分/续跑串单）；
3. 承办干事 cbbm1 当前可组合发起的预算计划分组及总数，是否够 跑 N 条 × plan-count。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from api.hp_api import find_request_by_name, get_purchase_request_page, get_user_info  # noqa: E402
from core import browser as browser_helpers  # noqa: E402
from core.config import Config  # noqa: E402
from core.session import BrowserSession, login_http  # noqa: E402
from pages.procurement_apply import ProcurementApplyPage  # noqa: E402


def check_pe_routes(session) -> None:
    print("\n[1] 采购执行服务（PE）鉴权接口")
    for path in (
        "/ProcurementExecution/purchase/purchaseProject/getPage?current=1&size=1",
        "/ProcurementExecution/purchase/purchaseProject/purchaseContactList",
    ):
        resp = session.api(path)
        body = resp.text[:160].replace("\n", " ")
        print(f"    {resp.status_code} {path} -> {body}")
    # 采购执行经办人候选：确认 --handler 指定的账号/姓名在候选里，以及默认“采购办经办人”对应哪个账号
    contacts = (session.api("/ProcurementExecution/purchase/purchaseProject/purchaseContactList")
                .json() or {}).get("list") or []
    print("    执行经办人候选："
          + "、".join(f"{c.get('username')}({c.get('contactName')})" for c in contacts))


def check_names(session, department_id: str, names: list[str]) -> None:
    print("\n[2] 采购申请名字占用情况")
    records = get_purchase_request_page(session, department_id, size=100)
    print(f"    本部门申请单（前 100 条）读取 {len(records)} 条")
    used = 0
    for name in names:
        hit = next((r for r in records if str(r.get("requestName") or "") == name), None)
        if hit is not None:
            used += 1
            print(f"    [占用] {name} -> {hit.get('requestCode')} status={hit.get('status')}")
        else:
            print(f"    [空闲] {name}")
    if used:
        print(f"    注意：{used} 个名字已被占用")


def check_plans(session, plan_count: int, runs: int) -> None:
    print(f"\n[3] 可组合发起的预算计划（每条 {plan_count} 个，共需 {plan_count * runs} 个）")
    page = ProcurementApplyPage(session)
    print(f"    首页可发起（单独发起按钮）：{page.selectable_plan_count()}")
    groups: dict[tuple, int] = {}
    page_no = 1
    while True:
        for group in page.selectable_plan_groups():
            key = (group[0]["type"], group[0]["gov"], group[0]["sme"])
            groups[key] = groups.get(key, 0) + len(group)
        sizes = {k: len(g) for k, g in zip(
            [(g[0]["type"], g[0]["gov"], g[0]["sme"]) for g in page.selectable_plan_groups()],
            page.selectable_plan_groups())}
        print(f"    第 {page_no} 页分组：{sizes}")
        if not page.next_page():
            break
        page_no += 1
    print(f"    合计分组（type,gov,sme -> 数量）：{groups}")
    best = max(groups.values()) if groups else 0
    print(f"    最大兼容组：{best} 个；需要：{plan_count * runs} 个 -> "
          f"{'足够' if best >= plan_count * runs else '不足'}（注：每页独立成组，跨页不可组合）")


def main() -> int:
    parser = argparse.ArgumentParser(description="线上全链前只读预检")
    parser.add_argument("--name", action="append", default=[], help="采购申请名字（可多次）")
    parser.add_argument("--plan-count", type=int, default=1)
    args = parser.parse_args()

    cfg = Config.load()
    print(f"环境：{cfg.environment} {cfg.base_url}")
    applicant = "cbbm1"
    http = login_http(applicant, cfg.password(applicant), "采购交易系统", cfg.base_url,
                      role_keyword="承办部门经办")
    info = get_user_info(http)
    department_id = info["organizationId"]
    print(f"账号：{applicant} role={http.role} departmentId={department_id}")

    check_pe_routes(http)
    if args.name:
        check_names(http, department_id, args.name)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = browser_helpers.launch(pw, cfg, headless=True)
        try:
            session = BrowserSession(browser, cfg, applicant, "采购交易系统",
                                      role_keyword="承办部门经办", use_cache=True)
            session.open()
            check_plans(session, args.plan_count, max(1, len(args.name)))
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
