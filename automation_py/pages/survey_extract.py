"""专家抽取页面（S11 全 UI 路径）：规划抽取 → 勾选专家 → 拨号登记。

页面链（均为 HCUI.popDialog 弹出的 iframe，宿主是「调研论证管理」列表页）：
- 列表行 ``lay-event="extract"`` → ``surveyArgument/extract.html``：规划表单，保存后手动抽选会自动弹勾选页；
- ``surveyArgument/pick.html``：候选表复选框 + ``#savePick``（提交并打电话）；
- 列表行 ``lay-event="manualDial"`` → ``surveyArgument/manualDial.html``：逐人点「参与」登记。

选择器依据 2026-11-27 版前端（openresty c29222ac）。
"""
from __future__ import annotations

import time

from core import browser as browser_helpers
from pages.common import READY_TIMEOUT_MS, click_row_event

EXTRACT_URL_PATTERN = "surveyArgument/extract.html"
PICK_URL_PATTERN = "surveyArgument/pick.html"
DIAL_URL_PATTERN = "surveyArgument/manualDial.html"
TIME_FMT = "%Y-%m-%d %H:%M:%S"


def _frame_exists(page, pattern: str) -> bool:
    return any(pattern in f.url for f in page.frames)


class SurveyExtractPage:
    def __init__(self, list_page, session):
        """list_page：已打开并搜索好的 SurveyArgumentPage。"""
        self.list_page = list_page
        self.session = session
        self.page = session.page
        self.frame = list_page.frame

    # ── 通用 ─────────────────────────────────────────────────
    def _select_radio(self, frame, name: str, value: str, required: bool = True) -> bool:
        """Layui 会重绘单选：点 input 后面的渲染节点，再校验原生 input 已选中。

        渲染节点由 form.render('radio') 在科室目录加载回调里生成，弹窗刚打开时可能还没有，
        因此先等它出现；旧版前端未重绘时才退回直接勾原生 input。
        """
        selector = f"input[name='{name}'][value='{value}']"
        target = frame.locator(selector)
        if target.count() == 0:
            if required:
                raise LookupError(f"规划页缺少单选项 {name}={value}")
            return False
        rendered = frame.locator(f"{selector} + .layui-form-radio")
        try:
            rendered.first.wait_for(state="visible", timeout=10000)
            rendered.first.click()
        except Exception:  # noqa: BLE001 - 未重绘时直接勾原生 input
            target.first.check(force=True)
        try:
            frame.wait_for_function(
                "(s) => { const el = document.querySelector(s); return !!el && el.checked; }",
                arg=selector, timeout=5000,
            )
        except Exception as exc:  # noqa: BLE001 - 带上选择器，便于定位
            raise AssertionError(f"规划页单选项未选中：{name}={value}") from exc
        return True

    @staticmethod
    def _set_readonly_date(frame, selector: str, value: str) -> None:
        """laydate 的 readonly 输入框不能 fill；页面提交时只读 .val()，直接设值即可。"""
        frame.evaluate(
            "([s, v]) => { const el = document.querySelector(s); if (!el) throw new Error('缺少 ' + s); el.value = v; }",
            [selector, value],
        )

    def _wait_frame(self, pattern: str, timeout_ms: int = READY_TIMEOUT_MS):
        return browser_helpers.get_frame(self.page, pattern, timeout_ms=timeout_ms)

    # ── 1. 规划抽取 ───────────────────────────────────────────
    def open_extract(self, project_name: str):
        click_row_event(self.page, self.frame, project_name, "extract")
        frame = self._wait_frame(EXTRACT_URL_PATTERN)
        frame.locator("#saveExtract").wait_for(state="visible", timeout=READY_TIMEOUT_MS)
        return frame

    def fill_plan(self, frame, *, dial_mode: str, gather_place: str, expert_count: int,
                  condition_key: str, condition_name: str, gather_minutes: int = 2,
                  gather_hours: float = 2) -> tuple[str, str]:
        """按人工口径填规划表：线下论证 / 手动抽选 / 指定通知方式 / 时间 / 地点 / 人数 / 条件。"""
        self._select_radio(frame, "argumentMode", "OFFLINE")
        self._select_radio(frame, "extractMode", "MANUAL")
        # 通知方式为 2026-11-26 新增控件；旧版前端没有时跳过，由调用方按 getDetail 回读结果分流
        self._select_radio(frame, "dialMode", dial_mode, required=False)

        start = time.strftime(TIME_FMT, time.localtime(time.time() + gather_minutes * 60))
        end = time.strftime(TIME_FMT, time.localtime(time.time() + gather_minutes * 60
                                                     + int(gather_hours * 3600)))
        self._set_readonly_date(frame, "#gatherTime", start)
        self._set_readonly_date(frame, "#gatherEndTime", end)
        frame.fill("#gatherPlace", gather_place)
        frame.fill("#evaluateExpertNumber", str(expert_count))

        row = frame.locator("#condBody .cond-row").first
        search = row.locator(".cond-major-search")
        search.click()
        if condition_name:
            search.fill(condition_name)
        item = row.locator(f".major-suggest-item[data-code='{condition_key}']")
        item.first.wait_for(state="visible", timeout=10000)
        item.first.click()
        picked = row.locator(".cond-major").first.get_attribute("value") or ""
        if picked != str(condition_key):
            raise AssertionError(f"规划页条件未选中：期望 {condition_key}，实际 {picked!r}")
        row.locator(".cond-count").fill(str(expert_count))
        return start, end

    def _read_msg(self, frame) -> str:
        """读取浮层提示；弹窗 iframe 在请求成功后会被页面自己关闭，读不到就返回空串。"""
        try:
            return browser_helpers.wait_for_msg(self.page, frame, timeout_ms=500)
        except Exception:  # noqa: BLE001 - Frame was detached 等同于弹窗已关闭
            return ""

    def save_plan(self, frame, timeout_ms: int = 30000):
        """点「保存并抽取」。成功后手动抽选会自动弹出勾选页；校验失败则弹提示并停留在本页。"""
        frame.locator("#saveExtract").click()
        deadline = time.time() + timeout_ms / 1000
        last_msg = ""
        while time.time() < deadline:
            if _frame_exists(self.page, PICK_URL_PATTERN):
                return "pick"
            if not _frame_exists(self.page, EXTRACT_URL_PATTERN):
                return "closed"
            last_msg = self._read_msg(frame) or last_msg
            self.page.wait_for_timeout(300)
        raise AssertionError(f"保存规划后未进入勾选页：{last_msg or '无提示信息'}")

    # ── 2. 勾选专家 ───────────────────────────────────────────
    def open_pick(self, project_name: str):
        """规划页没有自动弹勾选页时，从列表行「勾选专家」进入。"""
        self.list_page.search(project_name)
        click_row_event(self.page, self.frame, project_name, "pick")
        return self._wait_frame(PICK_URL_PATTERN)

    def pick_experts(self, pick_frame, count: int, timeout_ms: int = READY_TIMEOUT_MS) -> list[str]:
        boxes = pick_frame.locator("#candBody input[name='cand']:not([disabled])")
        deadline = time.time() + timeout_ms / 1000
        while boxes.count() < count and time.time() < deadline:
            self.page.wait_for_timeout(300)
        assert boxes.count() >= count, f"勾选页候选不足 {count} 人（{boxes.count()}）"
        picked = []
        for index in range(count):
            box = boxes.nth(index)
            box.check()
            picked.append(box.get_attribute("value") or "")
        pick_frame.locator("#pickedCount", has_text=f"已勾选 {count} 人").wait_for(timeout=5000)
        pick_frame.locator("#savePick").click()
        # 名额占满时页面自己关闭；手工拨号下提交后会自动弹出「拨号登记」并关闭本页；
        # 否则提示“已提交勾选…”留在本页等待继续勾选。轮询一律用 page 级等待，iframe 随时可能被关闭
        deadline = time.time() + timeout_ms / 1000
        msg = ""
        while time.time() < deadline:
            if not _frame_exists(self.page, PICK_URL_PATTERN):
                return picked
            msg = self._read_msg(pick_frame) or msg
            if "已提交勾选" in msg:
                return picked
            self.page.wait_for_timeout(300)
        raise AssertionError(f"提交勾选后页面未关闭：{msg or '无提示信息'}")

    # ── 3. 拨号登记 ───────────────────────────────────────────
    def dial_frame_or_open(self, project_name: str):
        """勾选页提交后若已自动弹出「拨号登记」则直接复用，否则从列表行进入。"""
        if _frame_exists(self.page, DIAL_URL_PATTERN):
            frame = self._wait_frame(DIAL_URL_PATTERN)
        else:
            frame = self.open_dial(project_name)
        frame.locator("#dialBody tr").first.wait_for(state="visible", timeout=READY_TIMEOUT_MS)
        return frame

    def open_dial(self, project_name: str):
        self.list_page.search(project_name)
        click_row_event(self.page, self.frame, project_name, "manualDial")
        return self._wait_frame(DIAL_URL_PATTERN)

    def register_all_agree(self, dial_frame, timeout_ms: int = READY_TIMEOUT_MS) -> int:
        """逐个点「参与」，直到页面提示抽取完成。返回登记人数。"""
        agree = dial_frame.locator("#dialBody button[data-act='AGREE']:not([disabled])")
        registered = 0
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            notice = dial_frame.locator("#dialNotice").inner_text() or ""
            if "抽取完成" in notice:
                return registered
            before = agree.count()
            if before == 0:
                dial_frame.wait_for_timeout(400)
                continue
            agree.first.click()
            registered += 1
            # 等这一行登记完成（按钮减少或页面提示完成）
            dial_frame.wait_for_function(
                """(before) => {
                    const n = document.querySelectorAll("#dialBody button[data-act='AGREE']:not([disabled])").length;
                    const notice = (document.getElementById('dialNotice') || {}).innerText || '';
                    return n < before || notice.indexOf('抽取完成') >= 0;
                }""",
                arg=before, timeout=15000,
            )
        notice = dial_frame.locator("#dialNotice").inner_text() or ""
        raise AssertionError(f"拨号登记未完成（已登记 {registered} 人）：{notice[:120]}")

    def close_dial(self, dial_frame) -> None:
        dial_frame.locator("#closeDial").click()
        deadline = time.time() + 10
        while time.time() < deadline and _frame_exists(self.page, DIAL_URL_PATTERN):
            self.page.wait_for_timeout(200)
