"""S08 供应商响应：3 家供应商参与调研并提交响应文件 + 技术参数。"""
from __future__ import annotations

from core.assert_helper import assert_true
from core.config import PACKAGE_ROOT
from pages.survey_project import SurveyProjectPage

RESPONSE_FILE = PACKAGE_ROOT / "fixtures" / "files" / "wjc测试文件.pdf"


def s08_supplier_reply(supplier_sessions: list, ctx: dict) -> dict:
    """依次用 3 家供应商提交调研响应，断言列表出现“查看提交调研资料”。"""
    assert_true(RESPONSE_FILE.exists(), f"响应文件不存在：{RESPONSE_FILE}")
    for index, session in enumerate(supplier_sessions, start=1):
        page = SurveyProjectPage(session)
        page.search(ctx["project_name"])
        assert_true(page.has_action(ctx["project_name"], "参与调研"),
                    f"供应商 {session.username} 未看到“参与调研”按钮")
        reply_frame = page.open_participate(ctx["project_name"])
        page.fill_supplier_reply(reply_frame, str(RESPONSE_FILE))
        page.submit_supplier_reply()
        page.search(ctx["project_name"])
        assert_true(page.has_action(ctx["project_name"], "查看提交调研资料"),
                    f"供应商 {session.username} 响应提交后未显示“查看提交调研资料”")
        print(f"[S08] 供应商 {index}/3 响应已提交：{session.username}")
    ctx["supplier_replies"] = len(supplier_sessions)
    return ctx
