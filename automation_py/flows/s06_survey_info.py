"""S06 完善调研信息：联系电话/起止时间/概况 + 三类评审指标。"""
from __future__ import annotations

from api.survey_api import SurveyApi
from core.assert_helper import assert_true
from flows.common import wait_until
from pages.survey_project import SurveyProjectPage


def s06_survey_info(session, ctx: dict) -> dict:
    """完善调研信息并保存，断言 infoComplete=1（可编辑公告）。"""
    api = SurveyApi(session)
    existing = api.find_project(ctx["project_name"])
    if existing and int(existing.get("infoComplete") or 0) == 1:
        print("[S06] 调研信息已是完善状态，跳过保存")
        ctx["survey_project_uuid"] = existing.get("uuid")
        ctx["survey_end_time"] = existing.get("endTime")
        return ctx

    page = SurveyProjectPage(session)
    page.search(ctx["project_name"])
    assert_true(page.has_action(ctx["project_name"], "完善信息")
                or page.has_action(ctx["project_name"], "编辑"),
                "调研项目列表未出现“完善信息/编辑”操作")

    edit_frame = page.open_edit(ctx["project_name"])
    page.fill_edit(edit_frame, end_minutes=ctx.get("survey_end_minutes", 7 * 24 * 60))
    page.save_edit()

    project = wait_until(
        lambda: (lambda p: p if p and int(p.get("infoComplete") or 0) == 1 else None)(
            api.find_project(ctx["project_name"])
        ),
        timeout_s=60,
        message="保存调研信息后 infoComplete 未变为 1",
    )
    print(f"[S06] 调研信息已保存，infoComplete={project.get('infoComplete')} OK")
    ctx["survey_project_uuid"] = project.get("uuid")
    ctx["survey_end_time"] = project.get("endTime")
    return ctx
