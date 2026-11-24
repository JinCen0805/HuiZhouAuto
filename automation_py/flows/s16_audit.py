"""S16 采购文件审计：推送审计 → 审计报告/审理 → 审计部主任通过 → status=20。

2026-11-24 起 HP 增加「承办部门主任复核」：
- 承办干事先初始化/保存审计报告初稿，再提交主任复核；
- 承办部门主任复核通过后才能选择审计员并推送；
- 推送后审计员在纪检平台审理，审计部主任审批。

实现说明：
- 审计报告初稿走 HP `/hospitalPurchaseAudit/{id}/report/*` 接口；
- 本地用同一 OnlyOffice 回调协议把报告标记为已保存（线上必须由编辑器真实保存）；
- 推送给审计员后，审理与主任审批仍走纪检平台接口（兼容 HP/纪检任一审计 ID）。
"""
from __future__ import annotations

import os

from api.audit_api import AuditApi
from api.audit_report import save_hp_report_via_callback
from api.document_api import (
    audit_auditor_candidates,
    audit_report_detail,
    audit_report_templates,
    audit_page,
    find_audit,
    init_audit_report,
    push_audit,
    review_audit_draft,
    submit_audit_draft,
)
from api.hp_api import get_purchase_request
from core.assert_helper import assert_true
from flows.common import wait_until


def _page_row(session, project_code: str) -> dict | None:
    return next((row for row in audit_page(session) if row.get("projectCode") == project_code), None)


def _pick_auditor(candidates: list[dict]) -> dict:
    target = next(
        (c for c in candidates if "审计员甲" in (c.get("userName") or "")),
        candidates[0] if candidates else None,
    )
    assert_true(target is not None, "没有可用的审计员候选人")
    return target


def _ensure_draft_and_push(hp_session, dept_director_session, audit: dict,
                           project_code: str) -> None:
    """承办干事保存初稿 → 提交主任复核 → 主任复核并推送审计员。"""
    audit_id = audit.get("uuid") or audit.get("auditId")
    detail = audit_report_detail(hp_session, audit_id)
    report = detail.get("report") or {}

    save_mode = os.environ.get("HP_AUDIT_SAVE_MODE", "auto").strip().lower()
    is_local = bool(getattr(getattr(hp_session, "cfg", None), "is_local", False))
    use_editor = (not is_local) or save_mode == "editor"
    if use_editor:
        # 线上由承办干事在 HP 审计初稿页的 OnlyOffice 编辑器里真实保存。
        from pages.audit_draft import AuditDraftPage

        AuditDraftPage(hp_session, audit_id).ensure_report_saved()
        detail = audit_report_detail(hp_session, audit_id)
        report = detail.get("report") or {}
    else:
        if not report.get("reportId"):
            templates = detail.get("templates") or audit_report_templates(hp_session, audit_id)
            assert_true(bool(templates), "没有可用的审计报告模板")
            template = templates[0]
            init_audit_report(hp_session, audit_id, template["templateId"])
            detail = audit_report_detail(hp_session, audit_id)
            report = detail.get("report") or {}
            print(f"[S16] 已生成审计报告初稿：{report.get('fileName')}")

        if int(report.get("reportStatus") or 0) != 2:
            save_hp_report_via_callback(hp_session, audit_id)
            print("[S16] 审计报告初稿已保存（本地回调）")
            detail = audit_report_detail(hp_session, audit_id)
            report = detail.get("report") or {}

    # 提交初稿；已提交过则复用列表行上的 submissionId
    row = _page_row(hp_session, project_code) or audit
    submission_id = row.get("draftSubmissionId") or ""
    if not submission_id:
        submission_id = submit_audit_draft(hp_session, audit_id, report)
        print(f"[S16] 审计初稿已提交承办部门主任复核：{submission_id}")
    else:
        print(f"[S16] 审计初稿已提交过，复用复核单：{submission_id}")
    assert_true(bool(submission_id), "审计初稿提交后未返回 submissionId")

    # 承办部门主任复核（由承办主任账号操作）
    director_row = _page_row(dept_director_session, project_code)
    passed = bool(director_row and director_row.get("draftReviewPassed"))
    if not passed:
        review_audit_draft(dept_director_session, audit_id, submission_id, approved=True)
        print("[S16] 承办部门主任已复核通过")
        director_row = _page_row(dept_director_session, project_code)

    candidates = audit_auditor_candidates(dept_director_session, audit_id, submission_id)
    auditor = _pick_auditor(candidates)
    pushed = push_audit(dept_director_session, audit_id, auditor["userId"],
                        submission_id=submission_id)
    print(f"[S16] 已推送审计：{pushed.get('auditCode')} → 审计员 {auditor.get('userName')}")


def _reserve_amounts(review: dict) -> list[dict]:
    """按预算计划生成审计数量/单价行；单计划与多计划都适用。"""
    rows: list[dict] = []
    for subpackage in review.get("subpackages") or []:
        for reserve in subpackage.get("reserveProjects") or []:
            reserve_id = reserve.get("reserveProjectId")
            if not reserve_id:
                continue
            quantity = reserve.get("quantity")
            unit_price = reserve.get("unitPrice")
            if quantity is None or unit_price is None:
                quantity = 1
                unit_price = reserve.get("budgetAmount") or 0
            rows.append({
                "reserveProjectId": reserve_id,
                "auditQuantity": quantity,
                "auditUnitPrice": unit_price,
            })
    return rows


def s16_audit(hp_session, auditor_session, audit_director_session,
              dept_director_session, ctx: dict) -> dict:
    """完成审计推送、报告保存、审理与主任审批，断言申请单 status=20。"""
    # 仅本地环境需要同步审计账号在纪检平台的登录 key（DB9→DB7）
    is_local = bool(getattr(getattr(hp_session, "cfg", None), "is_local", False))
    if is_local:
        try:
            from scripts.local_env import sync_redis_keys

            synced = sync_redis_keys(["sjyj", "sjbzr"])
            if synced:
                print(f"[S16] 本地 Redis key 同步：{synced}")
        except Exception as exc:  # noqa: BLE001 - 本地 docker 不可用时跳过
            print(f"[S16] Redis key 同步跳过：{exc}")

    current = get_purchase_request(hp_session, ctx["request_code"], ctx["department_id"])
    if current and int(current.get("status") or 0) in (19, 18, 10, 11, 9):
        print(f"[S16] 当前状态 {current.get('status')}，审计已完成，跳过")
        ctx["audit_passed"] = True
        return ctx

    audit = wait_until(
        lambda: find_audit(hp_session, ctx["request_code"]),
        timeout_s=20,
        message="未找到对应的采购审计记录",
    )
    audit_id = audit.get("uuid") or audit.get("auditId")
    assert_true(bool(audit_id), f"审计记录缺少 id：{audit}")
    audit_status = int(audit.get("auditStatus") or 0)

    if audit_status in (0, 6, 8):
        _ensure_draft_and_push(hp_session, dept_director_session, audit, ctx["request_code"])
        wait_until(
            lambda: (lambda r: r if r and int(r.get("auditStatus") or 0) == 1 else None)(
                find_audit(hp_session, ctx["request_code"])
            ),
            timeout_s=20,
            message="推送审计后审计状态未变为 1 审计中",
        )
        print("[S16] 审计已推送，进入审计员审理")
    elif audit_status == 1:
        print("[S16] 审计已在审计中，跳过初稿与推送")
    elif audit_status in (2, 3):
        print(f"[S16] 审计已到 {audit_status}，跳过初稿与推送")
    else:
        raise AssertionError(f"未识别的审计状态：{audit_status}")

    api = AuditApi(auditor_session)
    detail = api.detail(audit_id)
    status = int(detail.get("auditStatus") or 0)
    if status < 2:
        review = api.review(audit_id)
        report = review.get("report") or {}
        templates = review.get("templates") or []
        template_id = report.get("templateId") or (templates[0]["id"] if templates else "")
        assert_true(bool(template_id), "审计报告缺少模板，无法保存审理结果")
        api.save_review(
            audit_id,
            opinion="自动化测试审计意见：同意",
            template_id=template_id,
            audit_amount=float(detail.get("reportBudget") or 0),
            reserve_amounts=_reserve_amounts(review),
        )
        wait_until(
            lambda: (lambda d: d if d and int(d.get("auditStatus") or 0) == 2 else None)(
                api.detail(audit_id)
            ),
            timeout_s=20,
            message="保存审理结果后审计状态未进入 2 待主任审批",
        )
        print("[S16] 审计员审理完成，auditStatus=2 待主任审批")

    if int((api.detail(audit_id) or {}).get("auditStatus") or 0) < 3:
        director_api = AuditApi(audit_director_session)
        director_api.pass_director(audit_id, "自动化测试-审计通过")
        wait_until(
            lambda: (lambda d: d if d and int(d.get("auditStatus") or 0) == 3 else None)(
                director_api.detail(audit_id)
            ),
            timeout_s=20,
            message="审计部主任通过后审计状态未变为 3",
        )
        print("[S16] 审计部主任已通过，auditStatus=3")

    record = wait_until(
        lambda: (lambda r: r if r and int(r.get("status") or 0) in (19, 18, 10) else None)(
            get_purchase_request(hp_session, ctx["request_code"], ctx["department_id"])
        ),
        timeout_s=30,
        message="审计通过后申请单未进入待审查与方式分配",
    )
    print(f"[S16] 申请单状态={record.get('status')}（待审查与方式分配）OK")
    ctx["audit_passed"] = True
    return ctx
