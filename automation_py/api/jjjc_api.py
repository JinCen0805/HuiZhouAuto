"""纪检监察平台接口（分配监督员、分配查询）。"""
from __future__ import annotations

from urllib.parse import quote

PRJ_CODE_JJJC = "prjCode_PR_JJJC"


class JjjcApi:
    def __init__(self, session):
        self.session = session

    def list_supervisors(self) -> list[dict]:
        resp = self.session.api(
            f"/jjjc/supervise/supervisorList?prjCode={PRJ_CODE_JJJC}&pageNum=1&pageSize=50"
        )
        body = resp.json() or {}
        if not body.get("success", True):
            raise RuntimeError(f"监督员列表查询失败：{resp.status_code} {str(body)[:200]}")
        return body.get("data") or []

    def find_project(self, project_name: str) -> dict | None:
        resp = self.session.api(
            f"/jjjc/supervise/projectPageList?prjCode={PRJ_CODE_JJJC}"
            f"&projectName={quote(project_name)}&pageNum=1&pageSize=20"
        )
        body = resp.json() or {}
        if not body.get("success", True):
            raise RuntimeError(f"监察项目查询失败：{resp.status_code} {str(body)[:200]}")
        for row in body.get("data") or []:
            if row.get("requestName") == project_name:
                return row
        return None

    def assign_supervisor(self, project_id: str, supervisor_user_id: str,
                          supervision_scope: str = "1") -> dict:
        resp = self.session.api(
            "/jjjc/supervise/assign",
            method="POST",
            json={
                "projectId": project_id,
                "supervisorUserId": supervisor_user_id,
                "supervisionScope": supervision_scope,
            },
        )
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if not body.get("success"):
            raise RuntimeError(f"分配监督员失败：{resp.status_code} {str(body)[:300]}")
        return body

    def can_manage_assignment(self) -> bool:
        resp = self.session.api("/jjjc/supervise/canManageAssignment")
        return bool((resp.json() or {}).get("canManage"))
