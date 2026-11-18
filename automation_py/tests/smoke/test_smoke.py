"""WP1 冒烟测试（L1）：角色登录、页面可加载、关键接口可用。

覆盖：
- 5 个角色会话（承办部门干事/主任、纪检主任、审计员、供应商）
- 16 个核心页面（采购前置主链 + 纪检/审计页面）
- 关键接口：用户信息、预算计划、采购申请分页、纪检鉴权、审计分页
"""
from __future__ import annotations

import pytest

from core.assert_helper import assert_api_success, assert_contains, assert_true

pytestmark = pytest.mark.smoke


# ── 角色登录 ────────────────────────────────────────────────
@pytest.mark.parametrize("role", ["applicant", "director", "supervisor", "auditor", "supplier"])
def test_role_login(smoke_sessions, role):
    """角色可登录、角色名匹配、动态菜单非空。"""
    session = smoke_sessions[role]
    assert_true(session.role, f"{role} 角色名为空")
    menu = session.http.menu_json()
    items = menu.get("content") if isinstance(menu.get("content"), list) else []
    assert_true(bool(items), f"{role} 菜单为空：{str(menu)[:200]}")


# ── 页面可加载 ──────────────────────────────────────────────
# (role, 页面 URL, tab 标题, 页面应出现的关键字)
PAGES = [
    ("applicant", "/HospitalProcurement/view/procurementApply/list.html", "采购申请管理", "采购申请"),
    ("applicant", "/HospitalProcurement/view/packageManagement/index.html", "分包管理", "分包管理"),
    ("applicant", "/HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyProject/list.html", "调研项目管理", "采购项目类型"),
    ("applicant", "/HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyResult/list.html", "调研结果管理", "响应家数"),
    ("applicant", "/HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyArgument/list.html", "调研论证管理", "论证方式"),
    ("applicant", "/HospitalProcurement/view/procurementRequirement/index.html", "采购需求在线编制", "采购需求"),
    ("applicant", "/HospitalProcurement/view/auditManagement/index.html", "审计管理", "审计"),
    ("applicant", "/HospitalProcurement/view/procurementRequirementReview/index.html", "采购需求审查管理", "采购需求审查"),
    ("applicant", "/HospitalProcurement/view/procurementMethodConfirm/index.html", "采购方式分配", "采购方式"),
    ("applicant", "/HospitalProcurement/view/executionApply/list.html", "采购执行申请管理", "执行状态"),
    ("applicant", "/HospitalProcurement/view/procurementWorkbench/index.html", "采购工作台", "工作台"),
    ("supplier", "/HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyProject/list.html", "调研项目（供应商）", "参与情况"),
    ("supervisor", "/DisciplineInspection/view/projectList/index.html", "监察项目列表", "监督范围"),
    ("supervisor", "/DisciplineInspection/view/supervisorManage/index.html", "监督员管理", "监督员"),
    ("supervisor", "/DisciplineInspection/view/projectTrackingList/index.html", "申请单列表", "申请单"),
    ("auditor", "/DisciplineInspection/view/purchaseAudit/index.html", "采购专项审计", "审计"),
]


@pytest.mark.parametrize("role,url,title,keyword", PAGES)
def test_page_loads(smoke_sessions, role, url, title, keyword):
    """通过 changeView 打开页面，断言 iframe 内出现预期文案。"""
    session = smoke_sessions[role]
    try:
        frame = session.open_module(url, title)
        frame.wait_for_selector("body", timeout=15000)
        body = frame.locator("body").inner_text(timeout=15000)
        assert_contains(body, keyword, f"{title} 页面未出现关键字 {keyword!r}；body={body[:200]!r}")
    finally:
        # 关闭当前 tab 之外的页面：忽略错误，避免影响后续用例
        pass


# ── 关键接口 ────────────────────────────────────────────────
def test_api_user_basic_info(smoke_sessions):
    session = smoke_sessions["applicant"]
    resp = session.api("/HospitalProcurement/basicinfo/userinfo/getUserBasicInfo")
    assert_true(resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}")
    assert_api_success(resp.json(), "用户信息接口")


def test_api_reserve_library(smoke_sessions):
    session = smoke_sessions["applicant"]
    resp = session.api("/hospital-procurement/api/plan-management/reserve-library/years")
    assert_true(resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}")
    body = resp.json()
    assert_true(body.get("code") in (0, "0"), f"返回异常：{str(body)[:200]}")
    assert_true(isinstance(body.get("data"), list) and body["data"], "预算年度为空")


def test_api_purchase_request_page(smoke_sessions):
    session = smoke_sessions["applicant"]
    info = session.api("/HospitalProcurement/basicinfo/userinfo/getUserBasicInfo").json().get("data") or {}
    department_id = info.get("organizationId")
    assert_true(bool(department_id), f"用户信息缺少 organizationId：{str(info)[:200]}")
    resp = session.api(
        f"/HospitalProcurement/hospitalPurchaseRequest/page?current=1&size=5&departmentId={department_id}"
    )
    assert_true(resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}")
    assert_api_success(resp.json(), "采购申请分页接口")


def test_api_jjjc_auth(smoke_sessions):
    session = smoke_sessions["supervisor"]
    resp = session.api("/jjjc/supervise/canManageAssignment")
    assert_true(resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}")
    assert_api_success(resp.json(), "纪检鉴权接口")


def test_api_audit_page(smoke_sessions):
    session = smoke_sessions["auditor"]
    resp = session.api("/jjjc/purchaseAudit/page?auditStatus=1&pageNum=1&pageSize=5")
    assert_true(resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}")
    assert_api_success(resp.json(), "审计分页接口")
