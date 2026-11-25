#!/usr/bin/env python
"""线上全链结果只读核对：申请单状态、唯一性、预算计划/子包数量、采购方式落库、审计、执行项目。

用法（在 automation_py 目录）：
    $env:HP_ENV='online'; $env:HP_BASE_URL='http://172.16.29.215'
    python scripts/verify_online_result.py --code HW-YWB-CG20260209 --code FW-YWB-CG20260121 \
        --expect-method 2 --expect-plans 3

只做 GET 查询，不修改任何数据。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from api.audit_api import AuditApi  # noqa: E402
from api.document_api import find_audit  # noqa: E402
from api.execution_api import ExecutionApi  # noqa: E402
from api.hp_api import get_purchase_request, get_purchase_request_page, get_user_info  # noqa: E402
from core.config import Config  # noqa: E402
from core.session import login_http  # noqa: E402

METHOD_PREFIX = "/HospitalProcurement/hospitalPurchaseRequest/procurementMethod"


def amount_fields(record: dict) -> dict:
    return {k: v for k, v in record.items()
            if any(word in k.lower() for word in ("amount", "price", "budget"))
            and not isinstance(v, (dict, list))}


def main() -> int:
    parser = argparse.ArgumentParser(description="线上全链结果只读核对")
    parser.add_argument("--code", action="append", required=True, help="申请单号（可多次）")
    parser.add_argument("--expect-method", type=int, default=2, help="期望采购方式（默认 2 比选）")
    parser.add_argument("--expect-plans", type=int, default=1, help="期望预算计划数（默认 1）")
    args = parser.parse_args()

    cfg = Config.load()
    print(f"环境：{cfg.environment} {cfg.base_url}")
    applicant = login_http("cbbm1", cfg.password("cbbm1"), "采购交易系统", cfg.base_url,
                           role_keyword="承办部门经办")
    auditor = login_http("sjyj", cfg.password("sjyj"), "纪检监察平台", cfg.base_url,
                         role_keyword="审计员")
    department_id = get_user_info(applicant)["organizationId"]
    page_records = get_purchase_request_page(applicant, department_id, size=100)

    failures = 0
    rows = []
    for code in args.code:
        record = get_purchase_request(applicant, code, department_id)
        if record is None:
            print(f"\n[FAIL] {code} 未找到申请单")
            failures += 1
            continue
        name = str(record.get("requestName") or "")
        status = int(record.get("status") or 0)
        same_name = [r for r in page_records if str(r.get("requestName") or "") == name]
        request_id = record.get("uuid") or record.get("id")

        resp = applicant.api(f"{METHOD_PREFIX}/detail?purchaseRequestId={request_id}")
        method_detail = (resp.json() or {}).get("data") or {}
        subpackages = method_detail.get("subpackages") or []
        reserve_total = sum(len(s.get("reserveProjects") or []) for s in subpackages)
        method = method_detail.get("purchaseMethod")
        approval_status = method_detail.get("approvalStatus")

        audit = find_audit(applicant, code) or {}
        audit_subpackages = []
        audit_method = None
        audit_jjjc_status = None
        if audit.get("uuid") or audit.get("auditId"):
            # 已通过的审计不能再走 review（服务端拒绝“不能再次审理”），核对一律用 detail。
            audit_detail = AuditApi(auditor).detail(audit.get("uuid") or audit.get("auditId")) or {}
            audit_subpackages = audit_detail.get("subpackages") or []
            audit_method = audit_detail.get("procurementMethod")
            audit_jjjc_status = audit_detail.get("auditStatus")
        audit_reserve = [len(s.get("reserveProjects") or []) for s in audit_subpackages]

        execution = ExecutionApi(applicant).find_by_source_apply(request_id) or {}

        checks = {
            "status=9": status == 9,
            "唯一申请单": len(same_name) == 1,
            f"子包={args.expect_plans}": len(subpackages) == args.expect_plans,
            f"预算计划={args.expect_plans}": reserve_total == args.expect_plans,
            f"purchaseMethod={args.expect_method}": method == args.expect_method,
            "approvalStatus=3": approval_status == 3,
            "审计子包一致": audit_reserve == [len(s.get("reserveProjects") or []) for s in subpackages],
        }
        bad = [k for k, ok in checks.items() if not ok]
        failures += len(bad)
        print(f"\n[{('PASS' if not bad else 'FAIL')}] {code} {name}")
        print(f"    status={status} 同名申请单={len(same_name)} departmentId={record.get('departmentId')}")
        print(f"    金额字段：{amount_fields(record)}")
        print(f"    采购方式：purchaseCategory={method_detail.get('purchaseCategory')} "
              f"purchaseMethod={method} inHospitalPriceType={method_detail.get('inHospitalPriceType')} "
              f"approvalStatus={approval_status}")
        print(f"    子包 {len(subpackages)} 个，每个预算计划数 "
              f"{[len(s.get('reserveProjects') or []) for s in subpackages]}；"
              f"审计详情子包 {len(audit_subpackages)} 个，每个 {audit_reserve}")
        for sub in subpackages:
            sub_info = sub.get("subpackage") or sub
            for reserve in sub.get("reserveProjects") or []:
                print(f"      - 子包「{sub_info.get('subpackageName') or sub_info.get('packageName') or sub_info.get('uuid')}」"
                      f" 计划「{reserve.get('projectName') or reserve.get('reserveProjectName')}」"
                      f" 金额={reserve.get('budgetAmount')}")
        print(f"    审计：auditCode={audit.get('auditCode')} HP侧auditStatus={audit.get('auditStatus')} "
              f"纪检侧auditStatus={audit_jjjc_status} 审计侧采购方式={audit_method}")
        print(f"    执行项目：{execution.get('projectCode') or execution.get('projectNo') or ''} "
              f"state={execution.get('state')} name={execution.get('projectName') or execution.get('name')}")
        if bad:
            print(f"    未通过项：{bad}")
        rows.append((code, name, method, approval_status, len(subpackages), status))

    print("\n==== 汇总 ====")
    print("申请单号 | 项目名 | 方式 | 审批状态 | 子包数 | status")
    for row in rows:
        print(" | ".join(str(x) for x in row))
    print(f"结果：{'PASS' if failures == 0 else 'FAIL'}（未通过检查项 {failures}）")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
