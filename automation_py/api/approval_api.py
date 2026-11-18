"""审批流接口（Activiti）：待办查询 + 通用办理。"""
from __future__ import annotations

APPROVAL_PREFIX = "/EbiddingBusinessApproval/workflow"


class ApprovalApi:
    def __init__(self, session):
        self.session = session

    def list_todo(self, process_key: str | None = None, keyword: str | None = None,
                  current: int = 1, size: int = 20) -> list[dict]:
        params = {"current": current, "size": size}
        if process_key:
            params["processDefinitionKey"] = process_key
        if keyword:
            params["keyword"] = keyword
        query = "&".join(f"{k}={v}" for k, v in params.items())
        resp = self.session.api(f"{APPROVAL_PREFIX}/task/list/todo?{query}")
        body = resp.json() or {}
        if not body.get("success"):
            raise RuntimeError(f"待办查询失败：{resp.status_code} {str(body)[:300]}")
        data = body.get("data") or {}
        return data.get("records") or []

    def complete(self, task_id: str, audit_result: str = "1",
                 comment: str = "自动化测试-通过",
                 extra_form: dict | None = None) -> dict:
        """办理任务：auditResult=1 通过 / 0 驳回；extra_form 追加表单字段。"""
        data = {
            "taskId": task_id,
            "formProperties[auditResult]": audit_result,
            "comment": comment,
        }
        for key, value in (extra_form or {}).items():
            data[f"formProperties[{key}]"] = value
        resp = self.session.api(f"{APPROVAL_PREFIX}/task/complete", method="POST", data=data)
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if not body.get("success"):
            raise RuntimeError(f"办理任务失败：{resp.status_code} {str(body)[:300]}")
        return body
