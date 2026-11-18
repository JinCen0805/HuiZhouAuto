"""专家库 mock 回调（本地模拟“电话通知+专家按键确认”）。"""
from __future__ import annotations

MOCK_PREFIX = "/professor/expertExtract/mock"


class ProfessorMockApi:
    def __init__(self, session):
        self.session = session

    def enabled(self) -> bool:
        body = self.session.get(f"{MOCK_PREFIX}/enabled").json() or {}
        return bool((body.get("data") or {}).get("enabled"))

    def find_project(self, purchase_section_code: str) -> dict | None:
        body = self.session.get(
            f"{MOCK_PREFIX}/projects?keyword={purchase_section_code}&page=1&pageSize=10"
        ).json() or {}
        for row in (body.get("data") or {}).get("records") or []:
            if row.get("purchaseSectionCode") == purchase_section_code:
                return row
        return None

    def create_call_ids(self, project_id: str) -> list[dict]:
        body = self.session.post(
            f"{MOCK_PREFIX}/projects/{project_id}/callids", json={}
        ).json() or {}
        if not body.get("success"):
            raise RuntimeError(f"生成 callid 失败：{str(body)[:300]}")
        data = body.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("records") or [data]
        return []

    def callback(self, expert_id: str, call_id: str, keypress: str = "1") -> dict:
        body = self.session.post(
            f"{MOCK_PREFIX}/experts/{expert_id}/callback",
            json={"callid": call_id, "keypress": keypress},
        ).json() or {}
        if not body.get("success"):
            raise RuntimeError(f"专家按键回调失败：{str(body)[:300]}")
        return body
