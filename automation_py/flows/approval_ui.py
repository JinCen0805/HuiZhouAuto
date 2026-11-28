"""审批节点办理：默认走审批工作台 UI（待办 → 办理 → 通过 → 提交），``HP_APPROVAL_MODE=api`` 回落接口直调。

BT14 / BT6 / BT13 等所有审批节点共用；UI 路径按节点动态填写评标方式（BT6 采购办）与
采购执行经办人（BT13 采购办），接口路径沿用 formProperties / vars 参数。
"""
from __future__ import annotations

from api.approval_api import APPROVAL_PREFIX, ApprovalApi
from core.assert_helper import assert_true
from core.step_mode import use_ui


def approve_task(session, task: dict, comment: str, *, extra_form: dict | None = None,
                 bid_evaluation_form: str = "", handler_user_id: str = "",
                 ctx: dict | None = None) -> str:
    """办理一条待办任务（通过）。返回提示文案。"""
    if use_ui("APPROVAL", ctx):
        from pages.approval_workbench import ApprovalWorkbenchPage

        page = ApprovalWorkbenchPage(session)
        msg = page.complete(task["id"], comment, bid_evaluation_form=bid_evaluation_form,
                            handler_user_id=handler_user_id)
        print(f"[审批] 工作台办理通过（UI）：{task.get('name')} → {msg}")
        return msg

    if handler_user_id:
        # BT13 采购办主任：选采购执行经办人（接口口径与页面一致）
        data = {
            "taskId": task["id"],
            "formProperties[auditResult]": "1",
            "comment": comment,
            "vars[purchaseExecutionHandlerUserId]": handler_user_id,
        }
        resp = session.api(f"{APPROVAL_PREFIX}/task/complete", method="POST", data=data).json() or {}
        assert_true(bool(resp.get("success")), f"采购办主任选人失败：{str(resp)[:400]}")
        return "办理成功"
    ApprovalApi(session).complete(task["id"], "1", comment, extra_form)
    return "办理成功"
