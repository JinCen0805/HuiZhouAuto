"""HP 采购主引擎常用接口（列表/详情/用户信息）。"""
from __future__ import annotations


def get_user_info(session) -> dict:
    resp = session.api("/HospitalProcurement/basicinfo/userinfo/getUserBasicInfo")
    body = resp.json() or {}
    if not body.get("success"):
        raise RuntimeError(f"获取用户信息失败：{resp.status_code} {str(body)[:200]}")
    return body.get("data") or {}


def get_purchase_request(session, request_code: str, department_id: str) -> dict | None:
    """按申请单号查询采购申请记录（分页接口需要 departmentId）。"""
    resp = session.api(
        "/HospitalProcurement/hospitalPurchaseRequest/page"
        f"?current=1&size=50&requestCode={request_code}&departmentId={department_id}"
    )
    body = resp.json() or {}
    if not body.get("success"):
        raise RuntimeError(f"查询采购申请失败：{resp.status_code} {str(body)[:200]}")
    records = ((body.get("data") or {}).get("records")) or []
    for record in records:
        if record.get("requestCode") == request_code:
            return record
    return None
