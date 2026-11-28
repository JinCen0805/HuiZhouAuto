"""S19 采购方式分配 + BT6：承办干事提交 → 承办主任 → 采购办主任（按需选评标方式）
→ 院办主任；采购方式/议比价方式/唯一来源附件可通过环境变量或 ctx 选择。"""
from __future__ import annotations

from pathlib import Path

from api.approval_api import ApprovalApi
from api.hp_api import get_purchase_request, get_user_info
from api.method_api import MethodApi
from core.assert_helper import assert_true
from core.procurement_method import UNIQUENESS_ATTACHMENT_NAME, resolve
from core.step_mode import use_ui
from flows.approval_ui import approve_task
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

    basis = ctx.get("procurement_basis") or (
        f"自动化测试：根据项目属性、申请总金额和项目实际情况，选择{selection.name}。")
    # 断点续跑：方式已推送审批中（approvalStatus=1）时跳过提交，直接办理 BT6
    already_submitted = False
    try:
        detail = MethodApi(applicant_session).detail(record["uuid"])
        already_submitted = str(detail.get("approvalStatus")) == "1"
    except Exception as exc:  # noqa: BLE001 - 详情不可用时按未提交处理
        print(f"[S19] 查询方式分配详情失败，按未提交处理：{str(exc)[:120]}")
    if already_submitted:
        print("[S19] 采购方式已在审批中，跳过提交，直接办理 BT6")
    elif use_ui("S19", ctx):
        # 采购方式分配页：待分配申请行【分配方式】→ 弹窗选类别/方式/议比价方式/依据（→ 上传纪要）→ 推送主任审批
        from pages.procurement_method import ProcurementMethodPage

        attachment = ""
        if selection.uniqueness_attachment:
            path = Path(selection.uniqueness_attachment)
            if not path.is_file():
                raise FileNotFoundError(f"唯一性论证会议纪要文件不存在：{path}")
            attachment = str(path)
        ProcurementMethodPage(applicant_session).assign(
            record["requestCode"], selection.category, selection.method, basis,
            in_hospital_price_type=selection.in_hospital_price_type or "",
            attachment_path=attachment,
        )
    else:
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
        MethodApi(applicant_session).submit(
            record["uuid"],
            purchase_category=selection.category,
            purchase_method=selection.method,
            procurement_basis=basis,
            in_hospital_price_type=selection.in_hospital_price_type,
            bid_evaluation_form="",
            attachments=attachments,
        )
    if not already_submitted:
        print(f"[S19] 采购方式已提交（{selection.name}），进入 BT6")

    # BT6 三节点：顺序办理；ctx 记录已完成节点，重试/续跑时跳过（已办节点待办会消失）
    bid_form = selection.bid_evaluation_form if selection.needs_bid_evaluation_form else ""
    nodes = [
        ("node1", "承办部门主任", director_session, "自动化测试-方式分配主任审批通过", ""),
        ("node2", "采购办主任", procurement_director_session, "自动化测试-采购办主任审批", bid_form),
        ("node3", "院办主任", office_director_session, "自动化测试-院办主任审批", ""),
    ]
    done_nodes = ctx.setdefault("bt6_done", [])
    for pos, (key, label, session, comment, form) in enumerate(nodes):
        if key in done_nodes:
            print(f"[S19] BT6 {label} 已办理过，跳过")
            continue
        try:
            task = wait_until(lambda s=session: _bt6_task(s, record["uuid"]), timeout_s=25,
                              message=f"未找到 BT6 {label}待办")
        except TimeoutError:
            if any(_bt6_task(s, record["uuid"]) for _, _, s, _, _ in nodes[pos + 1:]):
                print(f"[S19] BT6 {label} 待办已消失且后续节点已出现，视为已办理，跳过")
                done_nodes.append(key)
                continue
            raise
        approve_task(session, task, comment, bid_evaluation_form=form, ctx=ctx)
        done_nodes.append(key)

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
