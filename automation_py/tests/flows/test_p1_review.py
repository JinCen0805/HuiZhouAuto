"""S08+S10 验收测试：供应商响应 → 资格性审查 → 待论证（state=4）。

自包含：先跑 P0 主链 + S06 调研信息 + S07 公告发布，再执行供应商响应与审查。
"""
from __future__ import annotations

import pytest

from flows.s01_apply import s01_apply
from flows.s04_supervisor import s04_supervisor
from flows.s05_package import s05_package
from flows.s06_survey_info import s06_survey_info
from flows.s07_notice import s07_notice
from flows.s08_supplier_reply import s08_supplier_reply
from flows.s10_review import s10_review

pytestmark = pytest.mark.p1


def test_supplier_reply_and_review(flow_sessions, config, run_id):
    applicant = flow_sessions["applicant"]
    supervisor = flow_sessions["supervisor"]
    director = flow_sessions["director"]
    suppliers = [flow_sessions["supplier1"], flow_sessions["supplier2"], flow_sessions["supplier3"]]

    ctx = {"run_id": run_id, "project_name": f"{run_id}-响应审查", "survey_end_minutes": 1.5}
    print(f"\n[P1] runId={ctx['run_id']}")

    # 前置：P0 主链 + 调研信息 + 公告发布
    s01_apply(applicant, ctx)
    s04_supervisor(supervisor, ctx)
    s05_package(applicant, ctx)
    s06_survey_info(applicant, ctx)
    s07_notice(applicant, ctx)

    # S08 供应商响应（3 家）
    s08_supplier_reply(suppliers, ctx)

    # S10 资格性审查
    s10_review(applicant, director, ctx)

    assert ctx.get("reviewed") is True
    print("\n[P1] 供应商响应与资格性审查通过（state=4 待论证）")
