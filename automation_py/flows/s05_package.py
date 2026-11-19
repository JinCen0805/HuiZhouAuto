"""S05 项目分包：新增子包 → 保存 → 确认锁定 → 断言待调研 + 调研项目生成。"""
from __future__ import annotations

from api.hp_api import get_purchase_request
from core.assert_helper import assert_status
from flows.common import wait_until
from pages.package_management import PackageManagementPage

SURVEY_MODULE_URL = (
    "/HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyProject/list.html"
)


def s05_package(session, ctx: dict) -> dict:
    """执行分包，断言 status=7 待调研、subpackageStatus=1，并验证调研项目生成。"""
    page = PackageManagementPage(session)
    page.search(ctx["project_name"])

    editor = page.open_editor(ctx["request_code"])
    subpackage_name = f"{ctx['run_id']}-子包01"
    page.add_subpackage(editor, subpackage_name)
    wait_until(
        lambda: page.editor_contains(editor, subpackage_name),
        timeout_s=20,
        message=f"新增子包后编辑页未出现子包名 {subpackage_name!r}",
    )
    print(f"[S05] 子包已保存：{subpackage_name}")
    page.close_editor()

    # 关闭编辑弹窗后列表刷新，重新搜索再确认
    page.search(ctx["project_name"])
    page.confirm_package(ctx["request_code"])

    record = wait_until(
        lambda: (lambda r: r if r and str(r.get("status")) == "7"
                 and int(r.get("subpackageStatus") or 0) == 1 else None)(
            get_purchase_request(session, ctx["request_code"], ctx["department_id"])
        ),
        timeout_s=25,
        message="分包确认后申请单未进入 待调研(7)/已分包",
    )
    assert_status(str(record.get("status")), "7", "S05 分包确认后状态应为 7 待调研")

    # 验证调研项目自动生成（列表页可见该申请单号）
    survey_frame = session.open_module(SURVEY_MODULE_URL, "调研项目管理", "0000001000001")
    survey_frame.wait_for_timeout(2500)
    body = survey_frame.locator("body").inner_text(timeout=10000)
    if ctx["request_code"] not in body:
        raise AssertionError(
            f"调研项目管理未找到申请单 {ctx['request_code']}；页面文本：{body[:300]!r}"
        )
    ctx["survey_project_verified"] = True
    print("[S05] 状态=7 待调研，调研项目已生成 OK")
    return ctx
