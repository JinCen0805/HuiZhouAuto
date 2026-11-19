"""S19 采购方式分配 + BT6：承办干事提交 → 承办主任 → 采购办主任（选评标方式）→ 院办主任。"""
from __future__ import annotations

from api.approval_api import ApprovalApi
from api.hp_api import get_purchase_request
from api.method_api import MethodApi
from core.assert_helper import assert_true
from flows.common import wait_until


def _bt6_task(session, request_uuid: str):
    api = ApprovalApi(session)
    return next(
        (t for t in api.list_todo(size=50)
         if t.get("businessKey") == f"BT6:{request_uuid}"),
        None,
    )


def s19_method(applicant_session, director_session, procurement_director_session,
               office_director_session, ctx: dict) -> dict:
    record = get_purchase_request(applicant_session, ctx["request_code"], ctx["department_id"])
    status = int(record.get("status") or 0)
    if status == 11:
        print("[S19] 当前状态 11，采购方式已审批完成，跳过")
        return ctx
    assert_true(status == 10,
                f"S19 前置状态应为 10 待分配采购方式，实际 {status}")
    MethodApi(applicant_session).submit(record["uuid"])
    print("[S19] 采购方式已提交（自主采购/比选采购），进入 BT6")

    # 节点1：承办部门主任
    task = wait_until(
        lambda: _bt6_task(director_session, record["uuid"]),
        timeout_s=30,
        message="未找到 BT6 承办部门主任待办",
    )
    ApprovalApi(director_session).complete(task["id"], "1", "自动化测试-方式分配主任审批通过")

    # 节点2：采购办主任选定评标方式（综合评分）
    task = wait_until(
        lambda: _bt6_task(procurement_director_session, record["uuid"]),
        timeout_s=30,
        message="未找到 BT6 采购办主任待办",
    )
    ApprovalApi(procurement_director_session).complete(
        task["id"], "1", "自动化测试-采购办主任审批",
        extra_form={"bidEvaluationForm": "0"},
    )

    # 节点3：院办主任
    task = wait_until(
        lambda: _bt6_task(office_director_session, record["uuid"]),
        timeout_s=30,
        message="未找到 BT6 院办主任待办",
    )
    ApprovalApi(office_director_session).complete(task["id"], "1", "自动化测试-院办主任审批")

    wait_until(
        lambda: (lambda r: r if r and int(r.get("status") or 0) == 11 else None)(
            get_purchase_request(applicant_session, ctx["request_code"], ctx["department_id"])
        ),
        timeout_s=40,
        message="BT6 通过后未进入 11 待发起采购执行",
    )
    print("[S19] 采购方式审批通过，status=11（待发起采购执行）OK")
    return ctx
