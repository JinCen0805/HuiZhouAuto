"""S13 线下论证：指定组长 → 上传论证报告 → 提交完成 → state=6 / 申请单 status=15。"""
from __future__ import annotations

import os

from api.hp_api import get_purchase_request
from api.survey_api import SurveyApi
from core.assert_helper import assert_true
from core.config import PACKAGE_ROOT
from flows.common import wait_until
from pages.survey_argument import SurveyArgumentPage

RESULT_FILE = PACKAGE_ROOT / "fixtures" / "files" / "wjc测试文件.pdf"


def s13_argument(session, ctx: dict) -> dict:
    """完成线下论证（指定组长 + 上传论证结果），断言 state=6、申请单 status=15。"""
    assert_true(RESULT_FILE.exists(), f"论证报告文件不存在：{RESULT_FILE}")
    from core import browser as browser_helpers

    browser_helpers.close_all_layers(session.page)
    api = SurveyApi(session)
    page = SurveyArgumentPage(session)
    page.search(ctx["project_name"])

    # 1) 指定组长（若列表操作栏出现“论证情况/指定组长”）
    if page.has_action(ctx["project_name"], "指定组长"):
        situation = page.open_situation(ctx["project_name"])
        expert_uuid = page.designate_first_leader(situation, ctx.get("survey_project_uuid", ""))
        print(f"[S13] 已指定组长：{expert_uuid}")
        page.search(ctx["project_name"])

    # 2) 等论证开始时间到达（线下论证结果须在论证开始后上传）
    gather_time = ctx.get("gather_time")
    if gather_time:
        import time
        from datetime import datetime

        gather_dt = datetime.strptime(str(gather_time)[:19], "%Y-%m-%d %H:%M:%S")
        deadline = time.time() + 240
        while datetime.now() < gather_dt:
            if time.time() > deadline:
                raise TimeoutError(f"等待论证开始超时（gatherTime={gather_time}）")
            remain = (gather_dt - datetime.now()).total_seconds()
            print(f"[S13] 等待论证开始：还剩 {remain:.0f}s")
            time.sleep(min(10, max(1, remain + 1)))

    # 论证开始后，列表操作栏才会出现“上传论证结果”
    def _upload_ready():
        page.search(ctx["project_name"])
        return page if page.has_action(ctx["project_name"], "上传论证结果") else None

    wait_until(_upload_ready, timeout_s=120, message="论证开始后仍未出现“上传论证结果”操作")

    # 3) 上传论证结果并提交
    assert_true(page.has_action(ctx["project_name"], "上传论证结果"),
                f"未出现“上传论证结果”操作；行文本={page.find_row(ctx['project_name']).inner_text()}")
    result_frame = page.open_result(ctx["project_name"])
    page.upload_and_submit(result_frame, str(RESULT_FILE))

    project = wait_until(
        lambda: (lambda p: p if p and int(p.get("state") or 0) == 6 else None)(
            api.find_project(ctx["project_name"])
        ),
        timeout_s=30,
        message="提交论证结果后调研项目未进入 state=6 论证完成",
    )
    print(f"[S13] 论证完成，state={project.get('state')} OK")

    record = wait_until(
        lambda: (lambda r: r if r and int(r.get("status") or 0) == 15 else None)(
            get_purchase_request(session, ctx["request_code"], ctx["department_id"])
        ),
        timeout_s=30,
        message="论证完成后采购申请未进入 15 待编制采购需求",
    )
    print(f"[S13] 申请单状态={record.get('status')}（待编制采购需求）OK")
    ctx["argument_done"] = True
    return ctx
