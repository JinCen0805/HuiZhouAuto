"""调研论证管理页（S13）：指定组长 → 线下论证结果上传并提交。"""
from __future__ import annotations

from core import browser as browser_helpers
from pages.common import click_row_event, find_row_by_text, wait_table_rows

MODULE_URL = (
    "/HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyArgument/list.html"
)
MENU_ID = "0000001000007"
SITUATION_URL_PATTERN = "surveyArgument/situation.html"
RESULT_URL_PATTERN = "surveyArgument/result.html"


class SurveyArgumentPage:
    def __init__(self, session):
        self.session = session
        self.page = session.page
        browser_helpers.close_all_layers(self.page)
        self.frame = session.open_module(MODULE_URL, "调研论证管理", MENU_ID)
        self.frame.locator("#doSearch").wait_for(state="visible", timeout=20000)
        self.frame.wait_for_timeout(1500)

    def search(self, project_name: str) -> None:
        # 打开模块/弹窗后可能遗留遮罩，搜索前再清理一次
        browser_helpers.close_all_layers(self.page)
        self.frame.locator("[idname='projectName']").fill(project_name)
        self.frame.click("#doSearch")
        self.frame.wait_for_timeout(1500)
        wait_table_rows(self.frame)

    def find_row(self, project_name: str):
        return find_row_by_text(self.frame, project_name)

    def has_action(self, project_name: str, action_text: str) -> bool:
        row = self.find_row(project_name)
        return row.locator("button", has_text=action_text).count() > 0

    # ── 指定组长 ─────────────────────────────────────────────
    def open_situation(self, project_name: str):
        click_row_event(self.page, self.frame, project_name, "situation")
        frame = browser_helpers.get_frame(self.page, SITUATION_URL_PATTERN)
        frame.locator("#closeSit").wait_for(state="visible", timeout=20000)
        return frame

    def designate_first_leader(self, situation_frame, survey_uuid: str = "") -> str:
        """读取候选专家组长的 data-uuid，直接调接口指定（避免异步弹窗时序问题）。"""
        from api.argument_api import ArgumentApi

        button = situation_frame.locator(".designate-btn").first
        button.wait_for(state="visible", timeout=15000)
        expert_uuid = button.get_attribute("data-uuid") or ""
        if not expert_uuid:
            raise LookupError("未读取到专家组长的 expertUuid")
        if survey_uuid:
            ArgumentApi(self.session).designate_leader(survey_uuid, expert_uuid)
        else:
            # 页面路径：「设为组长」会弹“确认指定该专家为组长？”二次确认
            button.click()
            browser_helpers.confirm_dialog(self.page, situation_frame)
            situation_frame.wait_for_timeout(2500)
            msg = browser_helpers.wait_for_msg(self.page, situation_frame, timeout_ms=3000)
            if "已指定组长" not in msg:
                raise AssertionError(f"页面指定组长未成功：{msg or '无提示信息'}")
        close = situation_frame.locator("#closeSit")
        if close.count() > 0:
            close.click()
        self.page.wait_for_timeout(1500)
        return expert_uuid

    # ── 线下论证结果 ─────────────────────────────────────────
    def open_result(self, project_name: str):
        click_row_event(self.page, self.frame, project_name, "offlineResult")
        frame = browser_helpers.get_frame(self.page, RESULT_URL_PATTERN)
        frame.locator("#resultFileSelect").wait_for(state="visible", timeout=20000)
        return frame

    def upload_and_submit(self, result_frame, pdf_path: str) -> None:
        file_input = result_frame.locator("#resultFileSelect input[type='file']")
        file_input.wait_for(state="attached", timeout=15000)
        file_input.set_input_files(pdf_path)
        upload_btn = result_frame.locator("#resultFileUploadBtn")
        if upload_btn.count() > 0 and upload_btn.is_visible():
            upload_btn.click()
        result_frame.wait_for_function(
            """() => {
                const list = document.querySelector('#resultFileList');
                return !!list && /已上传/.test(list.innerText || '');
            }""",
            timeout=60000,
        )
        result_frame.locator("#submitResult").click()
        browser_helpers.confirm_dialog(self.page, result_frame)
        for _ in range(60):
            if not any(RESULT_URL_PATTERN in f.url for f in self.page.frames):
                break
            self.page.wait_for_timeout(500)
