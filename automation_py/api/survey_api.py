"""市场调研项目接口：列表查询、立即发布。"""
from __future__ import annotations

SURVEY_PREFIX = "/HospitalProcurement/hpSurveyProject/hpSurveyProject"


class SurveyApi:
    def __init__(self, session):
        self.session = session

    def get_page(self, project_name: str = "", page: int = 1, limit: int = 20) -> list[dict]:
        resp = self.session.api(
            f"{SURVEY_PREFIX}/getPage",
            method="POST",
            data={"projectName": project_name, "page": page, "limit": limit},
        )
        body = resp.json() or {}
        if not body.get("success", True):
            raise RuntimeError(f"调研项目查询失败：{resp.status_code} {str(body)[:300]}")
        data = body.get("data") or {}
        return data.get("records") or []

    def find_project(self, project_name: str) -> dict | None:
        for row in self.get_page(project_name):
            if row.get("projectName") == project_name:
                return row
        return None

    def push_one_by_id(self, uuid: str) -> dict:
        """立即发布公告（pushOneById），无需等待定时任务。"""
        resp = self.session.api(
            f"{SURVEY_PREFIX}/pushOneById", method="POST", data={"uuid": uuid}
        )
        body = resp.json() or {}
        if not body.get("success"):
            raise RuntimeError(f"立即发布失败：{resp.status_code} {str(body)[:300]}")
        return body
