"""采购需求审查接口（HP 侧三阶段审查）。"""
from __future__ import annotations

REVIEW_PREFIX = "/HospitalProcurement/hospitalPurchaseDemandReview"


class DemandReviewApi:
    def __init__(self, session):
        self.session = session

    def initiate(self, purchase_request_id: str) -> str:
        body = self.session.api(
            f"{REVIEW_PREFIX}/initiate",
            method="POST",
            json={"purchaseRequestId": purchase_request_id},
        ).json() or {}
        if not body.get("success"):
            raise RuntimeError(f"发起需求审查失败：{str(body)[:400]}")
        return body.get("data") or ""

    def tasks(self, purchase_request_id: str) -> list[dict]:
        body = self.session.api(
            f"{REVIEW_PREFIX}/page?current=1&size=50&purchaseRequestId={purchase_request_id}"
        ).json() or {}
        return (body.get("data") or {}).get("records") or []

    def task_detail(self, task_id: str) -> dict:
        body = self.session.api(
            f"{REVIEW_PREFIX}/taskDetail?taskId={task_id}"
        ).json() or {}
        if not body.get("success"):
            raise RuntimeError(f"审查任务详情失败：{str(body)[:300]}")
        return body.get("data") or {}

    def complete(self, task_id: str, review_type: int, review_result: int = 1,
                 opinion: str = "自动化测试-审查通过") -> dict:
        detail = self.task_detail(task_id)
        task = detail.get("task") or {}
        payload = {
            "taskId": task_id,
            "documentId": task.get("reviewDocumentId"),
            "reviewType": review_type,
            "reviewResult": review_result,
            "reviewOpinion": opinion,
            "generalReview": {
                "nsResult": 1, "bmResult": 1, "prrResult": 1,
                "raaResult": 1, "pipResult": 1,
                "reviewResult": "通过",
                "reviewOpinion": "自动化测试-一般性审查通过",
            },
        }
        body = self.session.api(
            f"{REVIEW_PREFIX}/complete", method="POST", json=payload
        ).json() or {}
        if not body.get("success"):
            raise RuntimeError(f"提交审查结果失败：{str(body)[:400]}")
        return body
