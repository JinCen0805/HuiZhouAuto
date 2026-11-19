"""采购方式分配接口（HP 侧 + BT6）。"""
from __future__ import annotations

METHOD_PREFIX = "/HospitalProcurement/hospitalPurchaseRequest/procurementMethod"


class MethodApi:
    def __init__(self, session):
        self.session = session

    def submit(self, purchase_request_id: str, purchase_category: str = "1",
               purchase_method: str = "2",
               procurement_basis: str = "自动化测试：结合项目属性、金额与实际情况选择采购方式。",
               in_hospital_price_type: int | None = None,
               bid_evaluation_form: str = "",
               attachments: list[dict] | None = None) -> str:
        payload = {
            "purchaseRequestId": purchase_request_id,
            "purchaseCategory": purchase_category,
            "purchaseMethod": purchase_method,
            "bidEvaluationForm": bid_evaluation_form,
            "procurementBasis": procurement_basis,
        }
        if in_hospital_price_type is not None:
            payload["inHospitalPriceType"] = in_hospital_price_type
        if attachments:
            payload["attachments"] = attachments
        body = self.session.api(
            f"{METHOD_PREFIX}/submit", method="POST", json=payload
        ).json() or {}
        if not body.get("success"):
            raise RuntimeError(f"提交采购方式失败：{str(body)[:400]}")
        return body.get("data") or ""
