"""P0 主链测试：S01 采购申请 → S04 纪检分配 → S05 分包 → 生成调研项目。

验收标准（计划 WP2）：
- 生成 1 条“待调研”采购申请 + 自动生成的调研项目；
- 连续运行 2 次均通过（每次使用独立 runId，数据带前缀）。
"""
from __future__ import annotations

import pytest

from flows.s01_apply import s01_apply
from flows.s04_supervisor import s04_supervisor
from flows.s05_package import s05_package

pytestmark = pytest.mark.p0


def test_p0_main_chain(flow_sessions, config, run_id):
    """一条链跑通 S01→S04→S05，并断言关键状态。"""
    applicant = flow_sessions["applicant"]
    supervisor = flow_sessions["supervisor"]

    ctx = {
        "run_id": run_id,
        "project_name": f"{run_id}-采购申请",
    }
    print(f"\n[P0] runId={ctx['run_id']}")
    print(f"[P0] 项目名称={ctx['project_name']}")

    # S01：采购申请发起（计划内）
    s01_apply(applicant, ctx)
    assert ctx.get("request_code"), "S01 未产出申请单号"

    # S04：纪检分配监督员
    s04_supervisor(supervisor, ctx)

    # S05：分包 + 确认 + 调研项目生成
    s05_package(applicant, ctx)

    assert ctx.get("survey_project_verified") is True
    print("\n[P0] 主链通过：待调研 + 调研项目已生成")
