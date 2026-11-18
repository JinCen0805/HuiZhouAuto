"""S01 采购申请发起（计划内）：选预算计划 → 保存草稿 → 确认。"""
from __future__ import annotations

import time

from api.hp_api import get_purchase_request, get_user_info
from core.assert_helper import assert_status, assert_true
from flows.common import wait_until
from pages.procurement_apply import ProcurementApplyPage


def s01_apply(session, ctx: dict) -> dict:
    """执行采购申请发起，写入 ctx：request_code / department_id / plan_text。"""
    info = get_user_info(session)
    ctx["department_id"] = info.get("organizationId")
    assert_true(bool(ctx["department_id"]), f"用户信息缺少 organizationId：{str(info)[:200]}")

    page = ProcurementApplyPage(session)
    ctx["plan_text"] = page.first_selectable_plan_text()
    print(f"[S01] 选中预算计划：{ctx['plan_text'][:120]}")

    edit_frame = page.click_single_launch()
    page.fill_draft(edit_frame, {
        "project_name": ctx["project_name"],
        "purchase_content": "自动化测试采购内容：用于验证采购前置流程自动化的物资采购。",
        "application_reason": "自动化测试申请理由：科室业务需要，申请采购。",
    })
    page.save_draft()
    print(f"[S01] 草稿已保存：{ctx['project_name']}")

    page.open_applications_tab()
    ctx["request_code"] = page.request_code_of(ctx["project_name"])
    print(f"[S01] 申请单号：{ctx['request_code']}")

    page.confirm_application(ctx["project_name"])
    record = wait_until(
        lambda: (lambda r: r if r and r.get("status") == 22 else None)(
            get_purchase_request(session, ctx["request_code"], ctx["department_id"])
        ),
        timeout_s=20,
        message="确认后申请单未进入 待分配监督员(22)",
    )
    assert_status(str(record.get("status")), "22", "S01 确认后状态应为 22 待分配监督员")
    print("[S01] 状态=22 待分配监督员 OK")
    return ctx
