"""S20 采购执行申请 + BT13：草稿提交 → 承办主任 → 分管院领导 → 采购办主任（选经办人）
→ 分管领导 → 分管院领导 → status=9 采购中。"""
from __future__ import annotations

from api.approval_api import ApprovalApi
from api.execution_api import ExecutionApi
from api.hp_api import get_purchase_request
from core.assert_helper import assert_true
from flows.common import wait_until


def _execution_left_auditing(exec_api: ExecutionApi, project_uuid: str):
    """审批通过后执行项目会短暂停在 A4，必须等同步任务把它推离审批中。"""
    detail = exec_api.detail(project_uuid)
    execution = detail.get("execution") or {}
    state = str(execution.get("state") or "")
    return execution if state and state != "A4" else None


def _bt13_task(session, project_uuid: str):
    api = ApprovalApi(session)
    return next(
        (t for t in api.list_todo(size=50)
         if t.get("businessKey") == f"BT13:{project_uuid}"),
        None,
    )


def s20_execution(applicant_session, director_session, dept_leader_session,
                  procurement_director_session, vice_leader_session,
                  vice_president_session, ctx: dict) -> dict:
    record = get_purchase_request(applicant_session, ctx["request_code"], ctx["department_id"])
    status = int(record.get("status") or 0)
    if status == 9:
        print("[S20] 当前状态 9，采购前置已完成，跳过")
        ctx["procurement_started"] = True
        return ctx
    assert_true(status == 11,
                f"S20 前置状态应为 11 待发起采购执行，实际 {status}")
    exec_api = ExecutionApi(applicant_session)
    project = wait_until(
        lambda: exec_api.find_by_source_apply(record["uuid"]),
        timeout_s=20,
        message="未找到采购执行草稿项目",
    )
    project_uuid = project["uuid"]
    print(f"[S20] 执行草稿：{project.get('projectCode')} {project.get('projectName')}")
    exec_api.commit_audit(project_uuid)
    print("[S20] 已提交执行审批，进入 BT13")

    # 节点1：承办部门主任
    task = wait_until(lambda: _bt13_task(director_session, project_uuid), timeout_s=30,
                      message="未找到 BT13 承办部门主任待办")
    ApprovalApi(director_session).complete(task["id"], "1", "自动化测试-执行申请主任审批")

    # 节点2：承办部门分管院领导
    task = wait_until(lambda: _bt13_task(dept_leader_session, project_uuid), timeout_s=30,
                      message="未找到 BT13 分管院领导待办")
    ApprovalApi(dept_leader_session).complete(task["id"], "1", "自动化测试-分管院领导审批")

    # 节点3：采购办主任选采购执行经办人
    task = wait_until(lambda: _bt13_task(procurement_director_session, project_uuid),
                      timeout_s=30, message="未找到 BT13 采购办主任待办")
    contacts = exec_api.contact_list()
    handler_name = ctx.get("execution_handler") or "采购办经办人"
    handler = next((item for item in contacts
                    if handler_name in {
                        item.get("contactName"), item.get("username"), item.get("userId")
                    }), None)
    assert_true(handler is not None,
                f"未找到采购执行经办人 {handler_name}；候选："
                f"{[item.get('contactName') for item in contacts]}")
    approval = ApprovalApi(procurement_director_session)
    data = {
        "taskId": task["id"],
        "formProperties[auditResult]": "1",
        "comment": "自动化测试-采购办主任审批",
        "vars[purchaseExecutionHandlerUserId]": handler["userId"],
    }
    resp = procurement_director_session.api(
        "/EbiddingBusinessApproval/workflow/task/complete", method="POST", data=data
    ).json() or {}
    assert_true(bool(resp.get("success")), f"采购办主任选人失败：{str(resp)[:400]}")
    print(f"[S20] 采购办主任已指定执行经办人：{handler.get('contactName')}")

    # 节点4/5：分管领导、分管院领导
    for label, session in (("分管领导", vice_leader_session),
                           ("分管院领导", vice_president_session)):
        task = wait_until(lambda s=session: _bt13_task(s, project_uuid), timeout_s=30,
                          message=f"未找到 BT13 {label}待办")
        ApprovalApi(session).complete(task["id"], "1", f"自动化测试-{label}审批")
        print(f"[S20] {label}审批通过")

    status = wait_until(
        lambda: (lambda r: r if r and int(r.get("status") or 0) == 9 else None)(
            get_purchase_request(applicant_session, ctx["request_code"], ctx["department_id"])
        ),
        timeout_s=60,
        message="BT13 通过后申请单未进入 9 采购中",
    )
    print(f"[S20] 采购执行审批通过，申请单 status={status.get('status')}（采购中）")

    execution = wait_until(
        lambda: _execution_left_auditing(exec_api, project_uuid),
        timeout_s=90,
        message="采购申请已到采购中，但执行项目仍停在审批中",
    )
    print(f"[S20] 执行项目已离开审批中，state={execution.get('state')} OK")
    ctx["execution_project_uuid"] = project_uuid
    ctx["execution_state"] = execution.get("state")
    ctx["procurement_started"] = True
    return ctx
