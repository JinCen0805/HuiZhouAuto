"""S17 终稿确认：审计通过后再次提交 BT14，主任审批后进入 19 审查与方式分配。"""
from __future__ import annotations

from api.approval_api import ApprovalApi
from api.document_api import documents_of_request, second_confirmation
from api.hp_api import get_purchase_request
from core.assert_helper import assert_true
from flows.common import wait_until


def s17_final_confirmation(session, director_session, ctx: dict) -> dict:
    record = get_purchase_request(session, ctx["request_code"], ctx["department_id"])
    status = int(record.get("status") or 0)
    if status in (19, 18, 10, 11, 9):
        print(f"[S17] 当前状态 {status}，新流程无需二次确认，跳过")
        return ctx
    assert_true(status in (20, 16),
                f"S17 前置状态应为 20/16，实际 {status}")
    if status == 20:
        docs = documents_of_request(session, record["uuid"]).get("requirement") or {}
        document_uuid = docs.get("documentUuid") or ctx.get("requirement_doc_uuid")
        assert_true(bool(document_uuid), "未找到采购需求书文档")
        second_confirmation(session, record["uuid"], document_uuid)
        wait_until(
            lambda: (lambda r: r if r and int(r.get("status") or 0) == 16 else None)(
                get_purchase_request(session, ctx["request_code"], ctx["department_id"])
            ),
            timeout_s=20,
            message="终稿确认后未进入 16 编制文件审批中",
        )
        print("[S17] 终稿确认已提交，status=16")
    else:
        print("[S17] 状态 16：终稿确认已提交，直接办理主任审批")

    api = ApprovalApi(director_session)
    task = wait_until(
        lambda: next(
            (t for t in api.list_todo(size=30) if t.get("businessKey") == f"BT14:{record['uuid']}"),
            None,
        ),
        timeout_s=30,
        message="未找到终稿确认 BT14 待办",
    )
    api.complete(task["id"], "1", "自动化测试-终稿确认通过")
    wait_until(
        lambda: (lambda r: r if r and int(r.get("status") or 0) == 19 else None)(
            get_purchase_request(session, ctx["request_code"], ctx["department_id"])
        ),
        timeout_s=30,
        message="终稿确认审批后未进入 19 审查与方式分配",
    )
    print("[S17] 主任审批通过，status=19（待审查与方式分配）OK")
    return ctx
