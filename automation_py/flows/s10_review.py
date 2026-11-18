"""S10 资格性审查：干事逐家通过 → 提交主任 → 主任一键通过 → 提交结论（state=4）。"""
from __future__ import annotations

import time
from datetime import datetime

from api.survey_api import SurveyApi
from core.assert_helper import assert_true
from flows.common import wait_until
from pages.survey_result import SurveyResultPage


def wait_survey_deadline(ctx: dict, timeout_s: int = 240) -> None:
    """等到调研征集截止（结果审查的前置条件：截止后才能审核）。"""
    end_text = ctx.get("survey_end_time")
    if not end_text:
        return
    end_dt = datetime.strptime(str(end_text)[:19], "%Y-%m-%d %H:%M:%S")
    deadline = time.time() + timeout_s
    while datetime.now() <= end_dt:
        if time.time() > deadline:
            raise TimeoutError(f"等待调研截止超时（截止时间 {end_text}）")
        remain = (end_dt - datetime.now()).total_seconds()
        print(f"[S10] 等待调研征集截止：还剩 {remain:.0f}s")
        time.sleep(min(10, max(1, remain + 1)))


def s10_review(applicant_session, director_session, ctx: dict) -> dict:
    """完成资格性审查，断言调研项目 state 从 2 进入 4（待论证）。"""
    api = SurveyApi(applicant_session)

    # 0) 征集截止后才能审核
    wait_survey_deadline(ctx)

    # 1) 干事初审
    handler_page = SurveyResultPage(applicant_session)
    handler_page.search(ctx["project_name"])
    detail = handler_page.open_detail(ctx["project_name"])
    passed = handler_page.handler_pass_all(detail)
    assert_true(passed >= 1, f"未完成任何供应商初审（passed={passed}）")
    print(f"[S10] 干事初审通过 {passed} 家")

    # 2) 提交主任审批
    handler_page.submit_to_director("zhaoliu")
    wait_until(
        lambda: (lambda p: p if p and int(p.get("state") or 0) == 10 else None)(
            api.find_project(ctx["project_name"])
        ),
        timeout_s=20,
        message="提交主任审批后状态未进入 10 待部门主任审批",
    )
    print("[S10] 已提交主任审批，state=10")

    # 3) 主任一键通过 + 提交结论
    director_page = SurveyResultPage(director_session)
    director_page.search(ctx["project_name"])
    detail = director_page.open_detail(ctx["project_name"])
    director_page.director_pass_all(detail)
    director_page.director_finish(detail)

    project = wait_until(
        lambda: (lambda p: p if p and int(p.get("state") or 0) == 4 else None)(
            api.find_project(ctx["project_name"])
        ),
        timeout_s=25,
        message="主任提交评审结论后状态未进入 4 待完善论证信息",
    )
    print(f"[S10] 资格性审查完成，state={project.get('state')} OK")
    ctx["reviewed"] = True

    # 清理评审详情弹窗，避免遮挡后续页面
    from core import browser as browser_helpers

    browser_helpers.close_all_layers(applicant_session.page)
    browser_helpers.close_all_layers(director_session.page)
    return ctx
