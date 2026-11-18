"""S11+S13 验收测试（默认跳过：依赖本地 HP→professor 抽取建项 MQ 桥接）。

开启方式（本地栈修复后）：
    $env:HP_ARGUMENT_MQ_BRIDGE=1
    pytest tests/flows/test_p1_argument.py -v -s
"""
from __future__ import annotations

import os

import pytest

from flows.s01_apply import s01_apply
from flows.s04_supervisor import s04_supervisor
from flows.s05_package import s05_package
from flows.s06_survey_info import s06_survey_info
from flows.s07_notice import s07_notice
from flows.s08_supplier_reply import s08_supplier_reply
from flows.s10_review import s10_review
from flows.s11_extract import s11_extract
from flows.s13_argument import s13_argument
from pages.survey_argument import SurveyArgumentPage

pytestmark = pytest.mark.p1


def test_argument_page_readonly(flow_sessions):
    """调研论证管理页面可加载（只读，不依赖 MQ 桥接）。"""
    applicant = flow_sessions["applicant"]
    page = SurveyArgumentPage(applicant)
    assert page.frame.locator("#doSearch").is_visible()
    print("\n[P1] 调研论证管理页面加载 OK")


@pytest.mark.skipif(not os.getenv("HP_ARGUMENT_MQ_BRIDGE"),
                    reason="本地栈默认隔离 HP→professor 抽取建项 MQ 通道，需 HP_ARGUMENT_MQ_BRIDGE=1")
def test_argument_extract_and_offline(flow_sessions, config, run_id):
    applicant = flow_sessions["applicant"]
    supervisor = flow_sessions["supervisor"]
    director = flow_sessions["director"]
    suppliers = [flow_sessions["supplier1"], flow_sessions["supplier2"], flow_sessions["supplier3"]]

    ctx = {"run_id": run_id, "project_name": f"{run_id}-论证", "survey_end_minutes": 1.5}
    print(f"\n[P1] runId={ctx['run_id']}")

    s01_apply(applicant, ctx)
    s04_supervisor(supervisor, ctx)
    s05_package(applicant, ctx)
    s06_survey_info(applicant, ctx)
    s07_notice(applicant, ctx)
    s08_supplier_reply(suppliers, ctx)
    s10_review(applicant, director, ctx)

    s11_extract(applicant, ctx)
    s13_argument(applicant, ctx)

    assert ctx.get("argument_done") is True
    print("\n[P1] 专家抽取与线下论证通过（state=6 / status=15）")
