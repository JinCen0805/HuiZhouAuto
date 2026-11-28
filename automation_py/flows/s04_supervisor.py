"""S04 纪检主任分配监督员：查询待分配项目 → 分配（UI 默认 / 接口回退）→ 断言 22→8。"""
from __future__ import annotations

import time

from api.jjjc_api import JjjcApi
from core import browser as browser_helpers
from core.assert_helper import assert_true
from core.step_mode import use_ui
from flows.common import wait_until


def s04_supervisor(session, ctx: dict) -> dict:
    """执行纪检分配，断言申请单 requestStatus 由 22 变为 8。"""
    api = JjjcApi(session)
    project = wait_until(
        lambda: api.find_project(ctx["project_name"]),
        timeout_s=15,
        message="纪检平台未找到待分配项目",
    )
    print(f"[S04] 待分配项目：{project.get('requestCode')} status={project.get('requestStatus')}")

    supervisors = api.list_supervisors()
    candidates = [
        s for s in supervisors
        if s.get("supervisorUserId") and s.get("onDutyStatus") == "在岗"
    ]
    if not candidates:
        raise LookupError(f"没有在岗监督员：{str(supervisors)[:300]}")
    # 优先人工监督员（jjjdy*），避免选中系统管理员
    supervisor = next(
        (s for s in candidates if str(s.get("userName", "")).startswith("jjjdy")),
        candidates[0],
    )
    print(f"[S04] 监督员：{supervisor.get('legalContact')} ({supervisor.get('supervisorUserId')})")

    if use_ui("S04", ctx):
        # 纪检平台「监察项目列表」行【分配监督员】→ 弹窗选人 → 全流程 → 确认分配
        from pages.jjjc_project import JjjcProjectPage

        page = JjjcProjectPage(session)
        status = page.assign_supervisor(ctx["project_name"], supervisor["supervisorUserId"],
                                        supervisor.get("legalContact") or "")
        print(f"[S04] 已在监察项目列表分配监督员（UI），列表状态：{status}")
        browser_helpers.close_all_layers(session.page)
    else:
        api.assign_supervisor(project["uuid"], supervisor["supervisorUserId"], "1")

    updated = wait_until(
        lambda: (lambda p: p if p and str(p.get("requestStatus")) == "8" else None)(
            api.find_project(ctx["project_name"])
        ),
        timeout_s=15,
        message="分配监督员后项目未进入 8 待分包",
    )
    assert_true(str(updated.get("requestStatus")) == "8",
                f"分配后状态应为 8，实际 {updated.get('requestStatus')}")
    print("[S04] 状态=8 待分包 OK")
    return ctx
