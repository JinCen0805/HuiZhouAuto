"""审计接口（纪检平台侧）：查询、报告、审理、主任审批。"""
from __future__ import annotations

JJJC_AUDIT = "/jjjc/purchaseAudit"


class AuditApi:
    def __init__(self, session):
        self.session = session

    def page(self, audit_status: int | None = None, size: int = 20) -> list[dict]:
        query = f"pageNum=1&pageSize={size}"
        if audit_status is not None:
            query += f"&auditStatus={audit_status}"
        body = self.session.api(f"{JJJC_AUDIT}/page?{query}").json() or {}
        if not body.get("success"):
            raise RuntimeError(f"审计列表查询失败：{str(body)[:300]}")
        return (body.get("data") or {}).get("records") or []

    def review(self, audit_id: str) -> dict:
        body = self.session.api(f"{JJJC_AUDIT}/{audit_id}/review").json() or {}
        if not body.get("success"):
            raise RuntimeError(f"审计详情查询失败：{str(body)[:300]}")
        return body.get("data") or {}

    def detail(self, audit_id: str) -> dict:
        body = self.session.api(f"{JJJC_AUDIT}/{audit_id}/detail").json() or {}
        if not body.get("success"):
            raise RuntimeError(f"审计详情查询失败：{str(body)[:300]}")
        return body.get("data") or {}

    def init_report(self, audit_id: str, template_id: str) -> dict:
        body = self.session.api(
            f"{JJJC_AUDIT}/{audit_id}/report", method="POST", json={"templateId": template_id}
        ).json() or {}
        if not body.get("success"):
            raise RuntimeError(f"创建审计报告失败：{str(body)[:400]}")
        return body.get("data") or {}

    def save_review(self, audit_id: str, opinion: str, template_id: str,
                    audit_amount: float | None = None,
                    reserve_amounts: list[dict] | None = None) -> dict:
        payload = {
            "auditOpinion": opinion,
            "templateId": template_id,
            "reserveAmounts": reserve_amounts or [],
        }
        if audit_amount is not None:
            payload["auditAmount"] = audit_amount
        body = self.session.api(
            f"{JJJC_AUDIT}/{audit_id}/review", method="PUT", json=payload
        ).json() or {}
        if not body.get("success"):
            raise RuntimeError(f"保存审理结果失败：{str(body)[:400]}")
        return body.get("data") or {}

    def pass_director(self, audit_id: str, opinion: str = "自动化测试-审计通过") -> dict:
        body = self.session.api(
            f"{JJJC_AUDIT}/{audit_id}/pass",
            method="POST",
            json={"directorOpinion": opinion},
        ).json() or {}
        if not body.get("success"):
            raise RuntimeError(f"审计主任审批失败：{str(body)[:400]}")
        return body.get("data") or {}
