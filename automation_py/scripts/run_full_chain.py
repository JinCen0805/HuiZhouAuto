#!/usr/bin/env python
"""采购前置全链单入口：一条命令跑 P0→status=9，支持续跑/重试/报告。

用法（在 automation_py 目录）：
    python scripts/run_full_chain.py                     # 全新全链
    python scripts/run_full_chain.py --resume            # 找最近未完成申请续跑
    python scripts/run_full_chain.py --resume --request-code FW-YWB-CG20260123
    python scripts/run_full_chain.py --from S15          # 从指定步骤开始
    python scripts/run_full_chain.py --headed            # 显示浏览器
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.hp_api import find_latest_request, get_user_info  # noqa: E402
from core import browser as browser_helpers  # noqa: E402
from core.config import Config  # noqa: E402
from core.reporter import new_run_id  # noqa: E402
from core.session import BrowserSession  # noqa: E402
from flows.orchestrator import run_chain  # noqa: E402

from core.env_profile import accounts as _env_accounts

ROLE_SPECS = _env_accounts()



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="采购前置全链编排")
    parser.add_argument("--run-id", default="", help="运行标记；默认 UI自动化-时间戳")
    parser.add_argument("--project-name", default="", help="采购项目名称；默认 runId-全链")
    parser.add_argument("--applicant", default="", help="承办干事登录账号；默认 cbbm1")
    parser.add_argument("--handler", default="", help="采购执行经办人姓名或账号；默认 采购办经办人")
    parser.add_argument("--from", dest="start_from", default="S01",
                        help="起始步骤（S01/S04/.../S20）")
    parser.add_argument("--resume", action="store_true",
                        help="按申请单当前状态自动续跑")
    parser.add_argument("--request-code", default="",
                        help="续跑指定申请单号；不传则找最近一条 UI自动化-* 记录")
    parser.add_argument("--retries", type=int, default=1, help="失败重试次数")
    parser.add_argument("--purchase-method", default="",
                        help="采购方式：1 委托采购 / 2 比选采购(默认) / 3 竞争谈判 / 4 唯一来源 / 7 院内议比价")
    parser.add_argument("--plan-count", type=int, default=1,
                        help="一条申请单使用的预算计划数；>1 时走组合发起，并在分包阶段生成对应数量的子包")
    parser.add_argument("--plan-keyword", default="",
                        help="组合发起时先按预算计划名称过滤（例如本地种子计划）")
    parser.add_argument("--in-hospital-price-type", default="",
                        help="议比价方式：1 院内议价 / 2 院内比价（方式=7 时必填，默认 1）")
    parser.add_argument("--purchase-category", default="",
                        help="采购类别：0 政府采购 / 1 自主采购（默认按申请单自动判断）")
    parser.add_argument("--uniqueness-attachment", default="",
                        help="唯一来源谈判的唯一性论证会议纪要文件路径")
    parser.add_argument("--bid-evaluation-form", default="",
                        help="采购办主任评标方式：0 综合评分 / 1 最低评标价法（默认 0）")
    parser.add_argument("--headed", action="store_true", help="显示浏览器窗口")
    parser.add_argument("--keep-browser", action="store_true", help="结束后保留浏览器（调试）")
    return parser.parse_args()


def main() -> int:
    # 输出重定向到文件/管道时 Windows 默认用 GBK，编排日志里的 ▶/✓/✗ 会触发
    # UnicodeEncodeError 直接崩溃；降级为替换字符，保证 console.log 能完整落盘。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = parse_args()
    cfg = Config.load()
    if not cfg.is_local and os.environ.get("HP_ALLOW_ONLINE_WRITES") != "1":
        print("[CLI] 当前为线上环境，未设置 HP_ALLOW_ONLINE_WRITES=1，禁止执行写操作（全链会创建真实数据）。")
        return 2
    run_id = args.run_id or new_run_id()

    # 纪检/审计账号的登录 key 在本地 Redis 需要同步（DB9→DB7）
    try:
        from scripts.local_env import sync_redis_keys

        synced = sync_redis_keys(["jjzr", "sjyj", "sjbzr"])
        if synced:
            print(f"[CLI] Redis key 同步：{synced}")
    except Exception as exc:  # noqa: BLE001 - 非本地环境无需
        print(f"[CLI] Redis key 同步跳过：{exc}")

    from playwright.sync_api import sync_playwright

    sessions: dict[str, BrowserSession] = {}
    browser = None
    try:
        with sync_playwright() as pw:
            browser = browser_helpers.launch(pw, cfg, headless=not args.headed)
            role_specs = dict(ROLE_SPECS)
            if args.applicant:
                username, platform, role = role_specs["applicant"]
                role_specs["applicant"] = (args.applicant, platform, role)
            for key, (username, platform, role) in role_specs.items():
                print(f"[CLI] 登录 {key}: {username}（{platform}/{role}）")
                session = BrowserSession(
                    browser, cfg, username, platform,
                    role_keyword=role, use_cache=True,
                )
                session.open()
                sessions[key] = session

            info = get_user_info(sessions["applicant"])
            department_id = info["organizationId"]
            ctx = {
                "run_id": run_id,
                "project_name": args.project_name or f"{run_id}-全链",
                "department_id": department_id,
                "survey_end_minutes": 1.5,
                "execution_handler": args.handler or "采购办经办人",
                "plan_count": max(1, int(args.plan_count or 1)),
                "plan_keyword": args.plan_keyword or "",
            }
            if args.purchase_method:
                ctx["purchase_method"] = args.purchase_method
            if args.in_hospital_price_type:
                ctx["in_hospital_price_type"] = int(args.in_hospital_price_type)
            if args.purchase_category:
                ctx["purchase_category"] = args.purchase_category
            if args.uniqueness_attachment:
                ctx["uniqueness_attachment"] = args.uniqueness_attachment
            if args.bid_evaluation_form:
                ctx["bid_evaluation_form"] = args.bid_evaluation_form
            if args.request_code:
                ctx["request_code"] = args.request_code
            if args.resume:
                record = find_latest_request(
                    sessions["applicant"], department_id,
                    prefix="UI自动化-",
                )
                if record is None:
                    print("[CLI] 未找到可续跑的 UI自动化-* 申请，改为全新全链")
                else:
                    ctx["request_code"] = record["requestCode"]
                    ctx["project_name"] = record["requestName"]
                    print(f"[CLI] 续跑申请：{record['requestCode']} {record['requestName']}")

            result = run_chain(
                sessions, ctx=ctx, run_id=run_id,
                start_from=args.start_from, retries=args.retries,
                resume=args.resume,
            )
            print(f"\n[CLI] 结果：{result.status}，final_status={result.final_status}")
            print(f"[CLI] JSON 报告：{result.report_json}")
            print(f"[CLI] HTML 报告：{result.report_html}")
            return 0 if result.status == "success" else 1
    finally:
        if not args.keep_browser:
            for session in sessions.values():
                session.close()
            if browser is not None:
                try:
                    browser.close()
                except Exception:  # noqa: BLE001
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
