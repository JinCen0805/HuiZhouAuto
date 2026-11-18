"""采购执行申请接口（PE 侧）。"""
from __future__ import annotations

PE_PREFIX = "/ProcurementExecution/purchase/purchaseProject"


class ExecutionApi:
    def __init__(self, session):
        self.session = session

    def find_by_source_apply(self, source_apply_id: str) -> dict | None:
        body = self.session.api(
            f"{PE_PREFIX}/selectOne?sourceApplyId={source_apply_id}"
        ).json() or {}
        if not body.get("success"):
            return None
        return body.get("data") or None

    def contact_list(self) -> list[dict]:
        body = self.session.api(f"{PE_PREFIX}/purchaseContactList").json() or {}
        return body.get("list") or body.get("data") or []

    def commit_audit(self, project_uuid: str) -> str:
        body = self.session.api(
            f"{PE_PREFIX}/commitAudit", method="POST", data={"uuid": project_uuid}
        ).json() or {}
        if not body.get("success"):
            raise RuntimeError(f"提交执行审批失败：{str(body)[:400]}")
        return body.get("data") or ""

    def detail(self, project_uuid: str) -> dict:
        body = self.session.api(f"{PE_PREFIX}/detail?uuid={project_uuid}").json() or {}
        if not body.get("success"):
            raise RuntimeError(f"执行项目详情失败：{str(body)[:300]}")
        return body.get("data") or {}
