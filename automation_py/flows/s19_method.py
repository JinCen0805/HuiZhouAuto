"""S19 采购方式分配 + BT6：承办干事提交 → 承办主任 → 采购办主任（按需选评标方式）
→ 院办主任；采购方式/议比价方式/唯一来源附件可通过环境变量或 ctx 选择。"""
from __future__ import annotations

from pathlib import Path

from api.approval_api import ApprovalApi
from api.hp_api import get_purchase_request, get_user_info
from api.method_api import MethodApi
from core.assert_helper import assert_true
from core.procurement_method import UNIQUENESS_ATTACHMENT_NAME, resolve
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

    selection = resolve(record, ctx)
    print(f"[S19] 采购方式：{selection.category}/{selection.method} {selection.name}"
          + (f"，议比价方式={selection.in_hospital_price_type}" if selection.in_hospital_price_type else ""))

    attachments = None
    if selection.uniqueness_attachment:
        from core.office_files import upload_file

        path = Path(selection.uniqueness_attachment)
        if not path.is_file():
            raise FileNotFoundError(f"唯一性论证会议纪要文件不存在：{path}")
        user_id = get_user_info(applicant_session).get("userId")
        file_id = upload_file(path.read_bytes(), UNIQUENESS_ATTACHMENT_NAME, user_id,
                              "application/pdf")
        attachments = [{
            "fileId": file_id,
            "attachmentName": UNIQUENESS_ATTACHMENT_NAME,
            "attachmentType": "pdf",
            "attachmentSize": path.stat().st_size,
            "attachmentCategory": 2,
        }]
        print(f"[S19] 已上传唯一性论证会议纪要：{UNIQUENESS_ATTACHMENT_NAME}")

    basis = ctx.get("procurement_basis") or (
        f"自动化测试：根据项目属性、申请总金额和项目实际情况，选择{selection.name}。")
    MethodApi(applicant_session).submit(
        record["uuid"],
        purchase_category=selection.category,
        purchase_method=selection.method,
        procurement_basis=basis,
        in_hospital_price_type=selection.in_hospital_price_type,
        bid_evaluation_form="",
        attachments=attachments,
    )
    print(f"[S19] 采购方式已提交（{selection.name}），进入 BT6")

    # 节点1：承办部门主任
    task = wait_until(lambda: _bt6_task(director_session, record["uuid"]), timeout_s=30,
                      message="未找到 BT6 承办部门主任待办")
    ApprovalApi(director_session).complete(task["id"], "1", "自动化测试-方式分配主任审批通过")

    # 节点2：采购办主任（需要评标方式时选择）
    task = wait_until(lambda: _bt6_task(procurement_director_session, record["uuid"]),
                      timeout_s=30, message="未找到 BT6 采购办主任待办")
    extra_form = ({"bidEvaluationForm": selection.bid_evaluation_form}
                  if selection.needs_bid_evaluation_form else None)
    ApprovalApi(procurement_director_session).complete(
        task["id"], "1", "自动化测试-采购办主任审批", extra_form=extra_form)

    # 节点3：院办主任
    task = wait_until(lambda: _bt6_task(office_director_session, record["uuid"]),
                      timeout_s=30, message="未找到 BT6 院办主任待办")
    ApprovalApi(office_director_session).complete(task["id"], "1", "自动化测试-院办主任审批")

    wait_until(
        lambda: (lambda r: r if r and int(r.get("status") or 0) == 11 else None)(
            get_purchase_request(applicant_session, ctx["request_code"], ctx["department_id"])
        ),
        timeout_s=40,
        message="BT6 通过后未进入 11 待发起采购执行",
    )
    print(f"[S19] 采购方式审批通过（{selection.name}），status=11（待发起采购执行）OK")
    ctx["purchase_method"] = selection.method
    ctx["purchase_method_name"] = selection.name
    return ctx
