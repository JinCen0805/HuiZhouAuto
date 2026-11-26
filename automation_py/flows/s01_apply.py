"""S01 采购申请发起（计划内）：选预算计划 → 保存草稿 → 确认。"""
from __future__ import annotations

import time

from api.hp_api import find_request_by_name, get_purchase_request, get_user_info
from core.assert_helper import assert_status, assert_true
from flows.common import wait_until
from pages.procurement_apply import ProcurementApplyPage


def s01_apply(session, ctx: dict) -> dict:
    """执行采购申请发起，写入 ctx：request_code / department_id / plan_text。"""
    info = get_user_info(session)
    ctx["department_id"] = info.get("organizationId")
    assert_true(bool(ctx["department_id"]), f"用户信息缺少 organizationId：{str(info)[:200]}")

    # 同名申请防重：已存在（含草稿）直接报错，避免重复建单；续跑用 --resume --request-code。
    existing = find_request_by_name(session, ctx["department_id"], ctx["project_name"])
    assert_true(
        existing is None,
        f"同名采购申请已存在：{existing.get('requestCode') if existing else ''}"
        f"（status={existing.get('status') if existing else ''}），"
        f"请换名字或用 --resume --request-code 续跑",
    )

    page = ProcurementApplyPage(session)
    assert_true(page.selectable_plan_count() > 0, "没有可发起的预算计划（非本部门/已引用？）")
    plan_count = int(ctx.get("plan_count") or 1)
    if plan_count > 1:
        if ctx.get("plan_keyword"):
            page.search_plans(ctx["plan_keyword"])
        plans = None
        try:
            plans = page.compatible_plan_group(plan_count)
        except LookupError:
            # 第一页没有足够的兼容计划时，向后翻页继续找。
            for page_no in range(2, 11):
                if not page.next_page():
                    break
                try:
                    plans = page.compatible_plan_group(plan_count)
                    print(f"[S01] 第 {page_no} 页找到 {plan_count} 个兼容预算计划")
                    break
                except LookupError:
                    continue
        assert_true(plans is not None,
                    f"没有 {plan_count} 个可组合的预算计划（已翻页查找）：{ctx['project_name']}")
        ctx["plan_text"] = "、".join(p.get("text", "")[:40] for p in plans)
        edit_frame = page.combine_launch(plans)
        page.fill_draft(edit_frame, {
            "project_name": ctx["project_name"],
            "purchase_content": "自动化测试采购内容：用于验证采购前置流程自动化的物资采购。",
            "application_reason": "自动化测试申请理由：科室业务需要，申请采购。",
            "project_attribute": "1",
        })
        saved = page.save_draft()
        if not saved:
            draft = find_request_by_name(session, ctx["department_id"], ctx["project_name"])
            if draft and int(draft.get("status") or 0) == 0:
                saved = True
                page._close_all_layers()
                print("[S01] 草稿已落库（编辑弹窗未自动关闭，已按草稿确认）")
        assert_true(saved, f"组合发起（{plan_count} 个预算计划）保存草稿失败：{ctx['plan_text']}")
        print(f"[S01] 组合发起 {plan_count} 个预算计划：{ctx['plan_text'][:200]}")
    else:
        tried: set[str] = set()
        saved = False
        for _attempt in range(10):
            entries = page.selectable_plan_entries()
            candidate = next((e for e in entries if e["text"] not in tried), None)
            if candidate is None:
                break
            tried.add(candidate["text"])
            ctx["plan_text"] = candidate["text"]
            try:
                edit_frame = page.click_single_launch(candidate["index"])
            except Exception as exc:  # noqa: BLE001 - 列表刷新导致索引失效时跳过
                print(f"[S01] 打开计划失败，跳过：{str(exc)[:80]}")
                page.page.wait_for_timeout(800)
                continue
            page.fill_draft(edit_frame, {
                "project_name": ctx["project_name"],
                "purchase_content": "自动化测试采购内容：用于验证采购前置流程自动化的物资采购。",
                "application_reason": "自动化测试申请理由：科室业务需要，申请采购。",
            })
            if page.save_draft():
                saved = True
                print(f"[S01] 选中预算计划：{ctx['plan_text'][:120]}")
                break
            draft = find_request_by_name(session, ctx["department_id"], ctx["project_name"])
            if draft and int(draft.get("status") or 0) == 0:
                saved = True
                page._close_all_layers()
                print(f"[S01] 草稿已落库（编辑弹窗未自动关闭）：{ctx['plan_text'][:80]}")
                break
            print(f"[S01] 该预算计划不可用，尝试下一条：{ctx['plan_text'][:80]}")
        assert_true(saved, f"可发起预算计划均保存草稿失败（已尝试 {len(tried)} 条）")
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
