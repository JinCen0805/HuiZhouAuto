"""采购文件（需求书）与审计接口（HP 侧）。"""
from __future__ import annotations

PURCHASE_DOC = "/HospitalProcurement/purchase/document"
DOC_APPROVAL = "/HospitalProcurement/documentApproval"
HP_AUDIT = "/HospitalProcurement/hospitalPurchaseAudit"


def list_templates(session, purchase_request_id: str, document_type: str = "REQUIREMENT") -> list[dict]:
    body = session.api(
        f"{PURCHASE_DOC}/template/list?purchaseRequestId={purchase_request_id}"
        f"&documentType={document_type}"
    ).json() or {}
    if not body.get("success"):
        raise RuntimeError(f"模板列表查询失败：{str(body)[:300]}")
    return body.get("list") or (body.get("data") or {}).get("records") or (body.get("data") or {}).get("list") or []


def create_by_template(session, purchase_request_id: str, template_uuid: str,
                       document_type: str = "REQUIREMENT", idempotency_key: str = "") -> dict:
    body = session.api(
        f"{PURCHASE_DOC}/createByTemplate",
        method="POST",
        json={
            "purchaseRequestId": purchase_request_id,
            "documentType": document_type,
            "templateUuid": template_uuid,
            "idempotencyKey": idempotency_key or f"auto-{purchase_request_id}-{document_type}",
        },
    ).json() or {}
    if not body.get("success"):
        raise RuntimeError(f"创建采购文件失败：{str(body)[:400]}")
    return body.get("data") or {}


def confirm_save(session, document_uuid: str) -> dict:
    body = session.api(
        f"{PURCHASE_DOC}/{document_uuid}/confirm-save", method="POST", json={}
    ).json() or {}
    if not body.get("success"):
        raise RuntimeError(f"保存采购文件失败：{str(body)[:300]}")
    return body.get("data") or {}


def documents_of_request(session, purchase_request_id: str) -> dict:
    body = session.api(f"{PURCHASE_DOC}/by-purchase-request/{purchase_request_id}").json() or {}
    if not body.get("success"):
        raise RuntimeError(f"查询采购文件失败：{str(body)[:300]}")
    return body.get("data") or {}


def submit_draft(session, request_id: str, demand_document_id: str) -> dict:
    body = session.api(
        f"{DOC_APPROVAL}/submit-draft",
        method="POST",
        json={"requestId": request_id, "demandDocumentId": demand_document_id},
    ).json() or {}
    if not body.get("success"):
        raise RuntimeError(f"提交编制文件审批失败：{str(body)[:400]}")
    return body.get("data") or {}


def second_confirmation(session, request_id: str, demand_document_id: str) -> dict:
    body = session.api(
        f"{DOC_APPROVAL}/second-confirmation",
        method="POST",
        json={"requestId": request_id, "demandDocumentId": demand_document_id},
    ).json() or {}
    if not body.get("success"):
        raise RuntimeError(f"终稿确认提交失败：{str(body)[:400]}")
    return body.get("data") or {}


# ── HP 审计 ─────────────────────────────────────────────────
def audit_page(session, size: int = 100) -> list[dict]:
    body = session.api(f"{HP_AUDIT}/page?current=1&size={size}").json() or {}
    if not body.get("success"):
        raise RuntimeError(f"审计列表查询失败：{str(body)[:300]}")
    return (body.get("data") or {}).get("records") or []


def find_audit(session, project_code: str) -> dict | None:
    for row in audit_page(session):
        if row.get("projectCode") == project_code:
            return row
    return None


def push_audit(session, audit_id: str, auditor_user_id: str,
               submission_id: str = "",
               attach_requirement_document: int = 1) -> dict:
    body = session.api(
        f"{HP_AUDIT}/{audit_id}/push",
        method="POST",
        json={
            "auditorUserId": auditor_user_id,
            "attachRequirementDocument": attach_requirement_document,
            "submissionId": submission_id,
        },
    ).json() or {}
    if not body.get("success"):
        raise RuntimeError(f"推送审计失败：{str(body)[:400]}")
    return body.get("data") or {}


# ── HP 审计初稿（2026-11-24 承办主任复核流程） ────────────────
def audit_report_detail(session, audit_id: str) -> dict:
    body = session.api(f"{HP_AUDIT}/{audit_id}/report/detail").json() or {}
    if not body.get("success"):
        raise RuntimeError(f"审计报告详情查询失败：{str(body)[:400]}")
    return body.get("data") or {}


def audit_report_templates(session, audit_id: str) -> list[dict]:
    body = session.api(f"{HP_AUDIT}/{audit_id}/report/templates").json() or {}
    if not body.get("success"):
        raise RuntimeError(f"审计报告模板查询失败：{str(body)[:400]}")
    return body.get("list") or (body.get("data") or {}).get("templates") or []


def init_audit_report(session, audit_id: str, template_id: str) -> dict:
    body = session.api(
        f"{HP_AUDIT}/{audit_id}/report/initialize?templateId={template_id}",
        method="POST",
    ).json() or {}
    if not body.get("success"):
        raise RuntimeError(f"初始化审计报告失败：{str(body)[:400]}")
    return body.get("data") or {}


def submit_audit_draft(session, audit_id: str, report: dict) -> str:
    """承办干事提交已保存的审计初稿，返回 submissionId。"""
    report_id = report.get("reportId")
    file_id = report.get("fileId")
    version = report.get("reportVersion")
    if not (report_id and file_id and version):
        raise RuntimeError(f"审计报告缺少提交字段：{str(report)[:400]}")
    body = session.api(
        f"{HP_AUDIT}/{audit_id}/draft/submit?reportId={report_id}"
        f"&reportVersion={version}&fileId={file_id}",
        method="POST",
    ).json() or {}
    if not body.get("success"):
        raise RuntimeError(f"提交审计初稿失败：{str(body)[:400]}")
    return (body.get("data") or {}).get("submissionId") or ""


def review_audit_draft(session, audit_id: str, submission_id: str,
                       approved: bool = True, reason: str = "") -> dict:
    """承办部门主任复核审计初稿。"""
    query = f"submissionId={submission_id}&approved={'true' if approved else 'false'}"
    if reason:
        from urllib.parse import quote

        query += f"&reason={quote(reason)}"
    body = session.api(
        f"{HP_AUDIT}/{audit_id}/draft/review?{query}", method="POST"
    ).json() or {}
    if not body.get("success"):
        raise RuntimeError(f"审计初稿复核失败：{str(body)[:400]}")
    return body


def audit_auditor_candidates(session, audit_id: str, submission_id: str) -> list[dict]:
    body = session.api(
        f"{HP_AUDIT}/auditorCandidates?auditId={audit_id}&submissionId={submission_id}"
    ).json() or {}
    if not body.get("success"):
        raise RuntimeError(f"审计员候选人查询失败：{str(body)[:400]}")
    return body.get("data") or []
