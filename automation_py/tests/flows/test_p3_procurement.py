"""WP7 验收测试：S17 终稿确认 + S18 三方审查 + S19 方式分配 + S20 执行申请（自包含全链）。

运行条件：
    $env:HP_ARGUMENT_MQ_BRIDGE='1'
    $env:HP_FULL_CHAIN='1'
    pytest tests/flows/test_p3_procurement.py -v -s
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
from flows.s17_confirm import s17_final_confirmation
from flows.s18_review import s18_review
from flows.s19_method import s19_method
from flows.s20_execution import s20_execution

pytestmark = pytest.mark.p2

RUN_FULL = os.getenv("HP_FULL_CHAIN") == "1" and os.getenv("HP_ARGUMENT_MQ_BRIDGE") == "1"


@pytest.mark.skipif(not RUN_FULL, reason="需要 HP_FULL_CHAIN=1 且 HP_ARGUMENT_MQ_BRIDGE=1（全链约 8 分钟）")
def test_full_chain_to_procurement(flow_sessions, config, run_id):
    applicant = flow_sessions["applicant"]
    supervisor = flow_sessions["supervisor"]
    director = flow_sessions["director"]
    auditor = flow_sessions["auditor"]
    audit_director = flow_sessions["auditDirector"]
    suppliers = [flow_sessions["supplier1"], flow_sessions["supplier2"], flow_sessions["supplier3"]]

    ctx = {"run_id": run_id, "project_name": f"{run_id}-采购中", "survey_end_minutes": 1.5}
    print(f"\n[P3] runId={ctx['run_id']}")

    # 前置全链（与 WP5/WP6 相同）
    s01_apply(applicant, ctx)
    s04_supervisor(supervisor, ctx)
    s05_package(applicant, ctx)
    s06_survey_info(applicant, ctx)
    s07_notice(applicant, ctx)
    s08_supplier_reply(suppliers, ctx)
    s10_review(applicant, director, ctx)
    s11_extract(applicant, ctx)
    s13_argument(applicant, ctx)
    s15_requirement(applicant, director, ctx)
    s16_audit(applicant, auditor, audit_director, director, ctx)

    # WP7
    s17_final_confirmation(applicant, director, ctx)
    s18_review(
        applicant,
        director,
        flow_sessions["finance"],
        flow_sessions["hpAuditDirector"],
        flow_sessions["procurementDirector"],
        flow_sessions["jjjcDirector"],
        ctx,
    )
    s19_method(
        applicant,
        director,
        flow_sessions["procurementDirector"],
        flow_sessions["officeDirector"],
        ctx,
    )
    s20_execution(
        applicant,
        director,
        flow_sessions["deptLeader"],
        flow_sessions["procurementDirector"],
        flow_sessions["viceLeader"],
        flow_sessions["vicePresident"],
        ctx,
    )

    assert ctx.get("procurement_started") is True
    print("\n[P3] 采购前置全流程通过：status=9 采购中")
