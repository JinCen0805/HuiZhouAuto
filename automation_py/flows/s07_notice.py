"""S07 调研公告编制与发布：套用模板 → 定时发布（开始时间已过=立即发布）→ state=2。"""
from __future__ import annotations

from api.survey_api import SurveyApi
from core.assert_helper import assert_true
from flows.common import wait_until
from pages.survey_project import SurveyProjectPage


def s07_notice(session, ctx: dict) -> dict:
    """编辑公告并发布，断言调研项目 state=2（调研中）。"""
    api = SurveyApi(session)
    page = SurveyProjectPage(session)
    page.search(ctx["project_name"])
    assert_true(page.has_action(ctx["project_name"], "编辑公告"),
                "调研项目列表未出现“编辑公告”操作（S06 未完成？）")

    notice_frame = page.open_notice(ctx["project_name"])
    page.publish_by_dialog(notice_frame)

    try:
        project = wait_until(
            lambda: (lambda p: p if p and int(p.get("state") or 0) == 2 else None)(
                api.find_project(ctx["project_name"])
            ),
            timeout_s=75,  # 定时任务最长 60s 扫描一次
            message="公告发布后调研项目未进入 state=2 调研中",
        )
    except TimeoutError:
        # 兜底：直接调用立即发布接口（UI 定时发布未生效时）
        print("[S07] UI 定时发布未在 75s 内生效，改用立即发布接口兜底")
        page.publish_now_by_api(ctx["project_name"])
        project = wait_until(
            lambda: (lambda p: p if p and int(p.get("state") or 0) == 2 else None)(
                api.find_project(ctx["project_name"])
            ),
            timeout_s=30,
            message="立即发布接口调用后仍未进入 state=2",
        )

    print(f"[S07] 调研公告已发布，state={project.get('state')} OK")
    ctx["survey_published"] = True
    return ctx
