"""S16 采购文件审计：HP 推送审计 → 审计报告/审理 → 审计部主任通过 → status=20。

实现说明：
- 审计员侧默认走 API：initReport（模板渲染）→ 本地 OnlyOffice 回调（或真实编辑器保存）
  → saveReview；
- 审计部主任通过后 HP 申请单进入 20（审计通过待二次确认）。
"""
from __future__ import annotations

import os

from api.audit_api import AuditApi
from api.audit_report import save_report_via_callback
from api.document_api import auditor_candidates, find_audit, push_audit
from api.hp_api import get_purchase_request
from core.assert_helper import assert_true
from flows.common import wait_until


def _auditor_user_id(hp_session) -> str:
    candidates = auditor_candidates(hp_session)
    target = next(
        (c for c in candidates if "审计员甲" in (c.get("userName") or "")),
        candidates[0] if candidates else None,
    )
    assert_true(target is not None, "没有可用的审计员候选人")
    return target["userId"]


def s16_audit(hp_session, auditor_session, director_session, ctx: dict) -> dict:
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

    auditor_id = _auditor_user_id(hp_session)
    audit = wait_until(
        lambda: find_audit(hp_session, ctx["request_code"]),
        timeout_s=20,
        message="未找到对应的采购审计记录",
    )
    audit_id = audit.get("uuid") or audit.get("auditId")
    assert_true(bool(audit_id), f"审计记录缺少 id：{audit}")

    if int(audit.get("auditStatus") or 0) == 0:
        pushed = push_audit(hp_session, audit_id, auditor_id, attach_requirement_document=1)
        assert_true(int(pushed.get("auditStatus") or 0) == 1,
                    f"推送审计后状态异常：{pushed.get('auditStatus')}")
        print(f"[S16] 已推送审计：{pushed.get('auditCode')} → 审计中")

    api = AuditApi(auditor_session)
    review = api.review(audit_id)
    templates = review.get("templates") or []
    report = review.get("report") or {}
    if not report or not report.get("reportId"):
        assert_true(bool(templates), "没有可用的审计报告模板")
        template = templates[0]
        created = api.init_report(audit_id, template["id"])
        report = created.get("report") or {}
        print(f"[S16] 已生成审计报告：{report.get('fileName')}")

    # 保存审计报告：线上必须由 OnlyOffice 编辑器真实保存（不允许伪造回调）；
    # 本地为了免开编辑器，使用同一协议的本地回调落库。
    save_mode = os.environ.get("HP_AUDIT_SAVE_MODE", "auto").strip().lower()
    use_editor = (not is_local) or save_mode == "editor"
    if use_editor:
        from pages.audit_review import AuditReviewPage

        AuditReviewPage(auditor_session, audit_id).ensure_report_saved()
        print("[S16] 审计报告已保存（OnlyOffice 编辑器）")
    else:
        save_report_via_callback(auditor_session, audit_id)
        print("[S16] 审计报告已保存（本地回调）")

    detail = api.detail(audit_id)
    if int(detail.get("auditStatus") or 0) < 2:
        api.save_review(
            audit_id,
            opinion="自动化测试审计意见：同意",
            template_id=report.get("templateId") or (templates[0]["id"] if templates else ""),
            audit_amount=float(detail.get("reportBudget") or 0),
            reserve_amounts=[],
        )
        wait_until(
            lambda: (lambda d: d if d and int(d.get("auditStatus") or 0) == 2 else None)(
                api.detail(audit_id)
            ),
            timeout_s=20,
            message="保存审理结果后审计状态未进入 2 待主任审批",
        )
        print("[S16] 审计员审理完成，auditStatus=2 待主任审批")

    # 审计部主任通过
    director_api = AuditApi(director_session)
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
        lambda: (lambda r: r if r and int(r.get("status") or 0) == 20 else None)(
            get_purchase_request(hp_session, ctx["request_code"], ctx["department_id"])
        ),
        timeout_s=30,
        message="审计通过后申请单未进入 20 审计通过待二次确认",
    )
    print(f"[S16] 申请单状态={record.get('status')}（审计通过待二次确认）OK")
    ctx["audit_passed"] = True
    return ctx
