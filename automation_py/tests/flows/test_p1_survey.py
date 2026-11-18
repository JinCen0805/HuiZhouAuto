"""S06/S07 验收测试：P0 主链产生调研项目 → 完善调研信息 → 公告发布（state=2）。

说明：为保持自包含，本测试先跑一遍 P0 主链（约 20s）再继续调研阶段。
"""
from __future__ import annotations

import pytest

from flows.s01_apply import s01_apply
from flows.s04_supervisor import s04_supervisor
from flows.s05_package import s05_package
from flows.s06_survey_info import s06_survey_info
from flows.s07_notice import s07_notice

pytestmark = pytest.mark.p1


def test_survey_info_and_publish(flow_sessions, config, run_id):
    applicant = flow_sessions["applicant"]
    supervisor = flow_sessions["supervisor"]

    ctx = {"run_id": run_id, "project_name": f"{run_id}-调研项目"}
    print(f"\n[P1] runId={ctx['run_id']}")

    # 前置：P0 主链（申请→纪检→分包→生成调研项目）
    s01_apply(applicant, ctx)
    s04_supervisor(supervisor, ctx)
    s05_package(applicant, ctx)

    # S06 完善调研信息
    s06_survey_info(applicant, ctx)

    # S07 公告发布
    s07_notice(applicant, ctx)

    assert ctx.get("survey_published") is True
    print("\n[P1] 调研信息与公告发布通过")
