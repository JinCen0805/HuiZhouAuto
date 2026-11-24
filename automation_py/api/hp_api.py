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

def get_purchase_request_page(session, department_id: str, size: int = 100) -> list[dict]:
    """分页查询采购申请列表。"""
    resp = session.api(
        "/HospitalProcurement/hospitalPurchaseRequest/page"
        f"?current=1&size={size}&departmentId={department_id}"
    )
    body = resp.json() or {}
    if not body.get("success"):
        raise RuntimeError(f"查询采购申请列表失败：{resp.status_code} {str(body)[:200]}")
    return (body.get("data") or {}).get("records") or []

def find_latest_request(session, department_id: str, prefix: str = "UI自动化-") -> dict | None:
    """按项目名前缀查最近的采购申请（用于 --resume 续跑）。"""
    records = get_purchase_request_page(session, department_id, size=100)
    matches = [r for r in records if str(r.get("requestName") or "").startswith(prefix)]
    return matches[0] if matches else None


def find_request_by_name(session, department_id: str, name: str) -> dict | None:
    """按项目名精确查最近的采购申请（用于保存草稿后兜底确认）。"""
    records = get_purchase_request_page(session, department_id, size=100)
    matches = [r for r in records if str(r.get("requestName") or "") == name]
    return matches[0] if matches else None
