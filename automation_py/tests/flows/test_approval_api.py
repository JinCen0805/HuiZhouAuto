"""审批接口测试：待办只读校验 + 可选的办理验证（写操作需显式开关）。

写操作会推进本地一条真实待办，属于有副作用行为：
    $env:HP_APPROVAL_WRITE=1; pytest tests/flows/test_approval_api.py -v -s
不设置该环境变量时只做只读校验。
"""
from __future__ import annotations

import os

import pytest

from api.approval_api import ApprovalApi

pytestmark = pytest.mark.p1


def test_approval_todo_readonly(flow_sessions):
    """待办列表可查、字段完整（不产生任何写操作）。"""
    api = ApprovalApi(flow_sessions["director"])
    tasks = api.list_todo(size=10)
    assert isinstance(tasks, list), f"待办返回类型异常：{type(tasks)}"
    print(f"\n[审批] 待办数量={len(tasks)}")
    for task in tasks[:3]:
        print(f"  - {task.get('name')} | {task.get('processDefinitionName')} | id={task.get('id')}")
    if tasks:
        first = tasks[0]
        assert first.get("id"), f"待办缺少任务 id：{first}"
        assert first.get("processInstanceId"), f"待办缺少流程实例 id：{first}"


@pytest.mark.skipif(not os.getenv("HP_APPROVAL_WRITE"),
                    reason="未设置 HP_APPROVAL_WRITE=1，跳过有副作用的办理验证")
def test_approval_complete_one_task(flow_sessions):
    """对存量待办完成 1 次“通过”办理（需显式开启）。"""
    api = ApprovalApi(flow_sessions["director"])
    tasks = api.list_todo(size=10)
    assert tasks, "当前账号没有待办任务"
    task = tasks[0]
    print(f"\n[审批] 办理任务：{task.get('name')} id={task.get('id')}")
    result = api.complete(task["id"], audit_result="1", comment="自动化测试-通过")
    assert result.get("success") is True
    print("[审批] 办理成功 OK")
