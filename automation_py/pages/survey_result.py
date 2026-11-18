"""调研结果管理页（S10）：干事初审 → 提交主任 → 主任一键通过 → 提交结论。"""
from __future__ import annotations

from core import browser as browser_helpers
from pages.common import click_row_event, find_row_by_text, wait_table_rows

MODULE_URL = (
    "/HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyResult/list.html"
)
MENU_ID = "0000001000006"
DETAIL_URL_PATTERN = "surveyResult/detail.html"


class SurveyResultPage:
    def __init__(self, session):
        self.session = session
        self.page = session.page
        self.frame = session.open_module(MODULE_URL, "调研结果管理", MENU_ID)
        self.frame.locator("#doSearch").wait_for(state="visible", timeout=20000)
        self.frame.wait_for_timeout(1500)

    def search(self, project_name: str) -> None:
        self.frame.locator("[idname='projectName']").fill(project_name)
        self.frame.click("#doSearch")
        self.frame.wait_for_timeout(1500)
        wait_table_rows(self.frame)

    def find_row(self, project_name: str):
        return find_row_by_text(self.frame, project_name)

    # ── 打开评审详情 ─────────────────────────────────────────
    def open_detail(self, project_name: str):
        click_row_event(self.page, self.frame, project_name, "viewResult")
        frame = browser_helpers.get_frame(self.page, DETAIL_URL_PATTERN)
        frame.locator("#supplierPane").wait_for(state="visible", timeout=20000)
        # 等待供应商列表渲染
        frame.wait_for_function(
            "() => document.querySelectorAll('#supplierPane .supplier-item').length > 0",
            timeout=20000,
        )
        return frame

    # ── 干事：逐家通过 → 提交主任 ────────────────────────────
    def handler_pass_all(self, detail_frame) -> int:
        count = detail_frame.locator("#supplierPane .supplier-item").count()
        passed = 0
        for index in range(count):
            item = detail_frame.locator("#supplierPane .supplier-item").nth(index)
            item.click()
            detail_frame.wait_for_timeout(800)
            pass_btn = detail_frame.locator("#btnPass")
            if pass_btn.count() == 0 or not pass_btn.is_visible():
                continue  # 已审过/不允许
            pass_btn.click()
            browser_helpers.confirm_dialog(self.page, detail_frame)
            detail_frame.wait_for_timeout(1200)
            passed += 1
            print(f"[S10] 供应商 {index + 1}/{count} 初审通过")
        return passed

    def submit_to_director(self, director_keyword: str = "zhaoliu") -> None:
        button = self.page.locator("#btnSubmitDirector")
        # 按钮在 detail iframe 内
        detail = browser_helpers.get_frame(self.page, DETAIL_URL_PATTERN)
        if button.count() == 0:
            button = detail.locator("#btnSubmitDirector")
        button.last.wait_for(state="visible", timeout=10000)
        button.last.click()

        # 主任选择弹窗在 top
        select = self.page.locator("#pickSurveyDirectorSelect")
        select.wait_for(state="visible", timeout=10000)
        options = select.locator("option")
        chosen = None
        option_texts = []
        for i in range(options.count()):
            text = options.nth(i).inner_text()
            value = options.nth(i).get_attribute("value")
            option_texts.append(text)
            if value and director_keyword and director_keyword in text:
                chosen = value
                break
        if chosen is None:
            raise LookupError(
                f"未找到指定主任（关键字 {director_keyword!r}）；候选={option_texts}"
            )
        select.select_option(value=chosen)
        # 弹窗“确定”
        self.page.locator(".layui-layer-page .layui-layer-btn0").last.click()
        browser_helpers.confirm_dialog(self.page, None)
        self.page.wait_for_timeout(2000)
        detail.wait_for_timeout(1500)

    # ── 主任：一键通过 → 提交评审结论 ────────────────────────
    def director_pass_all(self, detail_frame) -> None:
        pass_all = detail_frame.locator("#btnDirectorPassAll")
        pass_all.wait_for(state="visible", timeout=15000)
        if pass_all.is_visible():
            pass_all.click()
            browser_helpers.confirm_dialog(self.page, detail_frame)
            detail_frame.wait_for_timeout(1500)

    def director_finish(self, detail_frame) -> None:
        finish = detail_frame.locator("#btnDirectorFinish")
        finish.wait_for(state="visible", timeout=15000)
        # 等待按钮可用
        for _ in range(30):
            if finish.is_enabled():
                break
            detail_frame.wait_for_timeout(500)
        finish.click()
        browser_helpers.confirm_dialog(self.page, detail_frame)
        detail_frame.wait_for_timeout(2000)
