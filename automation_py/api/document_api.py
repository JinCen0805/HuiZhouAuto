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


def auditor_candidates(session) -> list[dict]:
    body = session.api(f"{HP_AUDIT}/auditorCandidates").json() or {}
    return body.get("data") or []


def push_audit(session, audit_id: str, auditor_user_id: str,
               attach_requirement_document: int = 1) -> dict:
    body = session.api(
        f"{HP_AUDIT}/{audit_id}/push",
        method="POST",
        json={
            "auditorUserId": auditor_user_id,
            "attachRequirementDocument": attach_requirement_document,
        },
    ).json() or {}
    if not body.get("success"):
        raise RuntimeError(f"推送审计失败：{str(body)[:400]}")
    return body.get("data") or {}
