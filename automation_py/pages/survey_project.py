"""调研项目管理页（S06/S07）：完善调研信息 → 编辑公告 → 发布。"""
from __future__ import annotations

from datetime import datetime, timedelta

from core import browser as browser_helpers
from pages.common import click_row_event, find_row_by_text, wait_table_rows

MODULE_URL = (
    "/HospitalProcurement/view/hospitalProcurement/marketResearchManage/surveyProject/list.html"
)
MENU_ID = "0000001000001"
EDIT_URL_PATTERN = "surveyProject/edit.html"
NOTICE_URL_PATTERN = "surveyProject/notice.html"


def fmt_time(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def survey_time_window() -> tuple[str, str]:
    """调研起止时间：开始=1 小时前（触发立即发布），结束=7 天后。"""
    now = datetime.now()
    return fmt_time(now - timedelta(hours=1)), fmt_time(now + timedelta(days=7))


class SurveyProjectPage:
    def __init__(self, session):
        self.session = session
        self.page = session.page
        self.frame = session.open_module(MODULE_URL, "调研项目管理", MENU_ID)
        save_btn = self.frame.locator("#doSearch")
        save_btn.wait_for(state="visible", timeout=20000)
        self.frame.wait_for_timeout(1500)

    # ── 列表 ─────────────────────────────────────────────────
    def search(self, project_name: str) -> None:
        field = self.frame.locator("[idname='projectName']")
        field.fill(project_name)
        self.frame.click("#doSearch")
        self.frame.wait_for_timeout(1500)
        wait_table_rows(self.frame)

    def find_row(self, project_name: str):
        return find_row_by_text(self.frame, project_name)

    def has_action(self, project_name: str, action_text: str) -> bool:
        row = self.find_row(project_name)
        return row.locator("button", has_text=action_text).count() > 0

    # ── S06 完善调研信息 ──────────────────────────────────────
    def open_edit(self, project_name: str):
        click_row_event(self.page, self.frame, project_name, "edit")
        return browser_helpers.get_frame(self.page, EDIT_URL_PATTERN)

    def fill_edit(self, edit_frame, indicators: list[tuple[str, str, str]] | None = None) -> None:
        """填写调研信息：联系电话/起止时间/概况 + 三类评审指标各至少一条。"""
        start, end = survey_time_window()
        edit_frame.locator("[idname='handlerPhone']").wait_for(state="visible", timeout=15000)
        edit_frame.fill("[idname='handlerPhone']", "13800138000")
        edit_frame.fill("[idname='startTime']", start)
        edit_frame.fill("[idname='endTime']", end)
        edit_frame.fill("[idname='projectSummary']",
                        "自动化测试调研项目概况：用于验证采购前置流程自动化。")

        # 三类评审指标各新增一条（质量=1 / 安全=2 / 技术=3）
        rows = indicators or [
            ("1", "质量指标", "产品应符合国家及行业质量标准。"),
            ("2", "安全指标", "产品应满足医院安全使用要求。"),
            ("3", "技术指标", "产品技术参数应满足科室使用需求。"),
        ]
        for type_code, name, rule in rows:
            edit_frame.locator(f".index-tab[data-type='{type_code}']").click()
            edit_frame.wait_for_timeout(300)
            edit_frame.locator(".index-add").click()
            edit_frame.wait_for_timeout(500)
            pane = edit_frame.locator(f".index-pane.active .index-table[data-type='{type_code}']")
            pane.locator(".idx-name").last.fill(name)
            pane.locator(".idx-rule").last.fill(rule)
        edit_frame.wait_for_timeout(300)

    def save_edit(self) -> None:
        save_button = self.page.locator(".layui-layer-btn a", has_text="保存").last
        save_button.wait_for(state="visible", timeout=10000)
        save_button.click()
        # 等待编辑 iframe 关闭
        for _ in range(60):
            if not any(EDIT_URL_PATTERN in f.url for f in self.page.frames):
                break
            self.page.wait_for_timeout(500)

    # ── S07 编辑公告 / 发布 ──────────────────────────────────
    def open_notice(self, project_name: str):
        click_row_event(self.page, self.frame, project_name, "editNotice")
        frame = browser_helpers.get_frame(self.page, NOTICE_URL_PATTERN)
        self.wait_notice_ready(frame)
        return frame

    def wait_notice_ready(self, notice_frame, timeout_ms: int = 30000) -> None:
        """等待公告模板套用完成（标题 + 富文本内容非空）。"""
        notice_frame.wait_for_function(
            """() => {
                const title = document.querySelector('#bullentTitle');
                if (!title || !title.value.trim()) return false;
                if (window.bulletinEditor && typeof window.bulletinEditor.getContentTxt === 'function') {
                    return window.bulletinEditor.getContentTxt().trim().length > 0;
                }
                const content = document.querySelector('#bullentContent');
                return !!content && (content.value || '').replace(/<[^>]+>/g, '').trim().length > 0;
            }""",
            timeout=timeout_ms,
        )

    def publish_by_dialog(self, notice_frame) -> None:
        """点击公告弹窗第二按钮“定时发布”（开始时间已过 → 立即发布），并确认。"""
        button = self.page.locator(".layui-layer-btn a", has_text="定时发布").last
        button.wait_for(state="visible", timeout=10000)
        button.click()
        browser_helpers.confirm_dialog(self.page, None)
        self.page.wait_for_timeout(2000)
        msg = browser_helpers.wait_for_msg(self.page, None, timeout_ms=8000)
        if msg:
            print(f"[S07] 发布提示：{msg}")

    def publish_now_by_api(self, project_name: str) -> None:
        """兜底：直接调用立即发布接口（当 UI 定时发布未生效时使用）。"""
        from api.survey_api import SurveyApi

        api = SurveyApi(self.session)
        project = api.find_project(project_name)
        if not project:
            raise LookupError(f"调研项目不存在，无法发布：{project_name}")
        api.push_one_by_id(project["uuid"])
