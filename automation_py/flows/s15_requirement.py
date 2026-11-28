"""S15 采购需求文件编制：选模板 → 创建/保存需求书 → 提交编制审批（BT14）→ 待审计。"""
from __future__ import annotations

from api.document_api import (
    confirm_save,
    create_by_template,
    list_templates,
    submit_draft,
)
from api.hp_api import get_purchase_request
from api.approval_api import ApprovalApi
from core.assert_helper import assert_true
from flows.approval_ui import approve_task
from flows.common import wait_until


def _pick_template(templates: list[dict], government: bool, project_type) -> dict:
    """按项目类型/政采标识选内部采购模板。"""
    flag = "是" if government else "否"
    candidates = [
        t for t in templates
        if str(t.get("projectType")) == str(project_type)
        and str(t.get("governmentProcurement")) == flag
    ]
    assert_true(bool(candidates), f"未找到匹配模板（projectType={project_type}, gov={flag}）")
    return candidates[0]


def s15_requirement(session, director_session, ctx: dict) -> dict:
    """编制采购需求书并提交 BT14，断言申请单进入 17 待审计。"""
    record = get_purchase_request(session, ctx["request_code"], ctx["department_id"])
    assert_true(record is not None, f"申请单不存在：{ctx['request_code']}")
    status = int(record.get("status") or 0)
    if status not in (15, 16):
        print(f"[S15] 当前状态 {status}，编制阶段无需处理，跳过")
        return ctx
    assert_true(status in (15, 16), f"S15 前置状态应为 15/16，实际 {status}")
    government = str(record.get("governmentProcurement")) in ("是", "1", "true", "True")
    project_type = record.get("projectType")

    if status == 15:
        templates = list_templates(session, record["uuid"], "REQUIREMENT")
        template = _pick_template(templates, government, project_type)
        print(f"[S15] 选择模板：{template.get('sourceFileName') or template.get('templateCode')}")
        document = create_by_template(
            session, record["uuid"], template["uuid"], "REQUIREMENT",
            idempotency_key=f"{ctx['run_id']}-REQ",
        )
        document_uuid = document["documentUuid"]

        saved = confirm_save(session, document_uuid)
        assert_true(saved.get("documentStatus") == "SAVED", f"需求书保存失败：{saved}")
        print(f"[S15] 需求书已保存：{saved.get('fileName')}")
        submit_draft(session, record["uuid"], document_uuid)
        wait_until(
            lambda: (lambda r: r if r and int(r.get("status") or 0) == 16 else None)(
                get_purchase_request(session, ctx["request_code"], ctx["department_id"])
            ),
            timeout_s=20,
            message="提交编制审批后状态未进入 16 编制文件审批中",
        )
        print("[S15] 已提交编制文件审批，status=16")
    else:
        print("[S15] 状态 16：跳过创建，直接等待/推进主任审批")
        document_uuid = ctx.get("requirement_doc_uuid", "")

    # BT14 主任审批
    api = ApprovalApi(director_session)
    task = wait_until(
        lambda: next(
            (t for t in api.list_todo(size=30) if t.get("businessKey") == f"BT14:{record['uuid']}"),
            None,
        ),
        timeout_s=30,
        message="未找到 BT14 编制文件审批待办",
    )
    approve_task(director_session, task, "自动化测试-编制文件审批通过", ctx=ctx)
    approved = wait_until(
        lambda: (lambda r: r if r and int(r.get("status") or 0) in (17, 19, 18, 10) else None)(
            get_purchase_request(session, ctx["request_code"], ctx["department_id"])
        ),
        timeout_s=30,
        message="主任审批通过后状态未进入待审计或待审查",
    )
    print(f"[S15] 主任审批通过，status={approved.get('status')} OK")
    ctx["requirement_doc_uuid"] = document_uuid
    return ctx
