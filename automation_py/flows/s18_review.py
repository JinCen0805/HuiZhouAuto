"""S18 采购需求审查：承办主任选审查方式 → 财务/审计/采购并行审查 → 纪检主任终审。"""
from __future__ import annotations

from api.demand_review_api import DemandReviewApi
from api.hp_api import get_purchase_request
from core.assert_helper import assert_true
from core.step_mode import use_ui
from flows.common import wait_until


def _complete_stage(session, request_uuid: str, stage: int) -> int:
    api = DemandReviewApi(session)
    rows = [r for r in api.tasks(request_uuid) if r.get("currentStage") == stage
            and int(r.get("reviewStatus") or 1) == 1]
    for row in rows:
        api.complete(row["taskId"], review_type=1)
        print(f"[S18] 审查通过：{row.get('requestCode')} stage={stage}")
    return len(rows)


def s18_review(applicant_session, director_session, finance_session, audit_session,
               procurement_session, jjjc_session, ctx: dict) -> dict:
    record = get_purchase_request(applicant_session, ctx["request_code"], ctx["department_id"])
    status = int(record.get("status") or 0)
    assert_true(status in (19, 18),
                f"S18 前置状态应为 19/18，实际 {status}")
    request_uuid = record["uuid"]
    request_code = record.get("requestCode") or ctx["request_code"]

    if use_ui("S18", ctx):
        # 采购需求审查管理：干事【发起审查】→ 各审查人【审查】→ 一键通过 → 保存 → 确认通过
        from pages.demand_review import DemandReviewPage

        if status == 19:
            DemandReviewPage(applicant_session).initiate(request_code)
            print("[S18] 已发起需求审查（UI）")
        for name, session in (("承办部门主任", director_session), ("财务部", finance_session),
                              ("审计部", audit_session), ("采购部", procurement_session),
                              ("纪检主任", jjjc_session)):
            DemandReviewPage(session).review(request_code)
            print(f"[S18] {name}审查通过（UI）")
        wait_until(
            lambda: (lambda r: r if r and int(r.get("status") or 0) == 10 else None)(
                get_purchase_request(applicant_session, ctx["request_code"], ctx["department_id"])
            ),
            timeout_s=30,
            message="需求审查通过后未进入 10 待分配采购方式",
        )
        print("[S18] 三阶段审查通过（UI），status=10（待分配采购方式）OK")
        return ctx

    if status == 19:
        DemandReviewApi(applicant_session).initiate(request_uuid)
    wait_until(
        lambda: (lambda r: r if r and int(r.get("status") or 0) == 18 else None)(
            get_purchase_request(applicant_session, ctx["request_code"], ctx["department_id"])
        ),
        timeout_s=20,
        message="发起审查后未进入 18 审查中",
    )
    print("[S18] 已发起需求审查，status=18")

    # 阶段1：承办部门主任选择审查方式（一般性）并提交
    wait_until(
        lambda: bool(_complete_stage(director_session, request_uuid, 1)) or None,
        timeout_s=40,
        message="未出现承办部门主任审查任务",
    )
    # 阶段2：财务部/审计部/采购部并行
    for name, session in (("财务部", finance_session), ("审计部", audit_session),
                          ("采购部", procurement_session)):
        wait_until(
            lambda s=session: bool(_complete_stage(s, request_uuid, 2)) or None,
            timeout_s=40,
            message=f"{name}未出现需求审查任务",
        )
    # 阶段3：纪检主任终审
    wait_until(
        lambda: bool(_complete_stage(jjjc_session, request_uuid, 3)) or None,
        timeout_s=40,
        message="纪检主任未出现终审任务",
    )

    wait_until(
        lambda: (lambda r: r if r and int(r.get("status") or 0) == 10 else None)(
            get_purchase_request(applicant_session, ctx["request_code"], ctx["department_id"])
        ),
        timeout_s=30,
        message="需求审查通过后未进入 10 待分配采购方式",
    )
    print("[S18] 三阶段审查通过，status=10（待分配采购方式）OK")
    return ctx
