"""采购方式分配接口（HP 侧 + BT6）。"""
from __future__ import annotations

METHOD_PREFIX = "/HospitalProcurement/hospitalPurchaseRequest/procurementMethod"


class MethodApi:
    def __init__(self, session):
        self.session = session

    def submit(self, purchase_request_id: str, purchase_category: str = "1",
               purchase_method: str = "2",
               procurement_basis: str = "自动化测试：结合项目属性、金额与实际情况选择比选采购。") -> str:
        payload = {
            "purchaseRequestId": purchase_request_id,
            "purchaseCategory": purchase_category,
            "purchaseMethod": purchase_method,
            "bidEvaluationForm": "",
            "procurementBasis": procurement_basis,
        }
        body = self.session.api(
            f"{METHOD_PREFIX}/submit", method="POST", json=payload
        ).json() or {}
        if not body.get("success"):
            raise RuntimeError(f"提交采购方式失败：{str(body)[:400]}")
        return body.get("data") or ""
