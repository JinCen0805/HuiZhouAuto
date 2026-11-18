"""WP6 验收测试：S15 需求编制 + S16 审计（自包含全链，默认跳过）。

运行条件（本地已按 WP5/WP6 修复环境）：
    $env:HP_ARGUMENT_MQ_BRIDGE='1'
    $env:HP_FULL_CHAIN='1'
    pytest tests/flows/test_p2_requirement_audit.py -v -s
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
from flows.s15_requirement import s15_requirement
from flows.s16_audit import s16_audit

pytestmark = pytest.mark.p2

RUN_FULL = os.getenv("HP_FULL_CHAIN") == "1" and os.getenv("HP_ARGUMENT_MQ_BRIDGE") == "1"


@pytest.mark.skipif(not RUN_FULL, reason="需要 HP_FULL_CHAIN=1 且 HP_ARGUMENT_MQ_BRIDGE=1（全链约 10 分钟）")
def test_requirement_and_audit(flow_sessions, config, run_id):
    applicant = flow_sessions["applicant"]
    supervisor = flow_sessions["supervisor"]
    director = flow_sessions["director"]
    auditor = flow_sessions["auditor"]
    audit_director = flow_sessions["auditDirector"]
    suppliers = [flow_sessions["supplier1"], flow_sessions["supplier2"], flow_sessions["supplier3"]]

    ctx = {"run_id": run_id, "project_name": f"{run_id}-需求审计", "survey_end_minutes": 1.5}
    print(f"\n[P2] runId={ctx['run_id']}")

    # 前置全链：申请 → 纪检 → 分包 → 调研 → 响应 → 审查 → 论证
    s01_apply(applicant, ctx)
    s04_supervisor(supervisor, ctx)
    s05_package(applicant, ctx)
    s06_survey_info(applicant, ctx)
    s07_notice(applicant, ctx)
    s08_supplier_reply(suppliers, ctx)
    s10_review(applicant, director, ctx)
    s11_extract(applicant, ctx)
    s13_argument(applicant, ctx)

    # S15 需求编制 + BT14
    s15_requirement(applicant, director, ctx)

    # S16 审计
    s16_audit(applicant, auditor, audit_director, ctx)

    assert ctx.get("audit_passed") is True
    print("\n[P2] 需求编制与审计通过（status=20 审计通过待二次确认）")
