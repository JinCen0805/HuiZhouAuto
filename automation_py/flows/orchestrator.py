"""全链编排：按步骤顺序执行 P0→status=9，支持断点续跑、失败重试与运行报告。

步骤函数统一为 `run(ctx) -> ctx`，由 `build_steps(sessions)` 按账号组装。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

from api.hp_api import find_latest_request, get_purchase_request
from core.reporter import Reporter, new_run_id
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

# 采购申请状态 → 续跑起始步骤
STATUS_TO_STEP = {
    22: "S04",
    8: "S05",
    7: "S06",
    2: "S07",
    4: "S10",
    15: "S15",
    16: "S15",
    17: "S16",
    # 新流程审计与编制并行，待审计时仍要先确保需求书已编制。
    # 各步骤内部会按当前状态跳过已完成动作。
    20: "S17",
    19: "S18",
    18: "S18",
    10: "S19",
    11: "S20",
}

@dataclass
class Step:
    step_id: str
    name: str
    run: object
    retryable: bool = True


@dataclass
class ChainResult:
    run_id: str
    status: str
    steps: list = field(default_factory=list)
    report_json: str = ""
    report_html: str = ""
    final_status: int | None = None
    error: str = ""


def build_steps(sessions: dict) -> list[Step]:
    S = sessions
    return [
        Step("S01", "创建采购申请（提交审批并自动通过）",
             lambda ctx: s01_apply(S["applicant"], ctx), retryable=False),
        Step("S04", "纪检主任分配监督员",
             lambda ctx: s04_supervisor(S["supervisor"], ctx)),
        Step("S05", "承办干事分包确认",
             lambda ctx: s05_package(S["applicant"], ctx)),
        Step("S06", "完善调研信息",
             lambda ctx: s06_survey_info(S["applicant"], ctx)),
        Step("S07", "发布调研公告",
             lambda ctx: s07_notice(S["applicant"], ctx)),
        Step("S08", "供应商响应（3 家）",
             lambda ctx: s08_supplier_reply(
                 [S["supplier1"], S["supplier2"], S["supplier3"]], ctx)),
        Step("S10", "资格性审查（干事初审 + 主任审批）",
             lambda ctx: s10_review(S["applicant"], S["director"], ctx)),
        Step("S11", "专家抽取（线下+手动+mock 确认）",
             lambda ctx: s11_extract(S["applicant"], ctx)),
        Step("S13", "线下论证（指定组长+上传报告）",
             lambda ctx: s13_argument(S["applicant"], ctx)),
        Step("S15", "采购需求书编制 + BT14",
             lambda ctx: s15_requirement(S["applicant"], S["director"], ctx)),
        Step("S16", "采购文件审计（初稿复核/推送/审理/主任通过）",
             lambda ctx: s16_audit(
                 S["applicant"], S["auditor"], S["auditDirector"], S["director"], ctx)),
        Step("S17", "终稿确认 + BT14",
             lambda ctx: s17_final_confirmation(S["applicant"], S["director"], ctx)),
        Step("S18", "三方需求审查（财务/审计/采购/纪检）",
             lambda ctx: s18_review(
                 S["applicant"], S["director"], S["finance"], S["hpAuditDirector"],
                 S["procurementDirector"], S["jjjcDirector"], ctx)),
        Step("S19", "采购方式分配 + BT6",
             lambda ctx: s19_method(
                 S["applicant"], S["director"], S["procurementDirector"],
                 S["officeDirector"], ctx)),
        Step("S20", "采购执行申请 + BT13",
             lambda ctx: s20_execution(
                 S["applicant"], S["director"], S["deptLeader"],
                 S["procurementDirector"], S["viceLeader"], S["vicePresident"], ctx)),
    ]


def resolve_resume(applicant_session, department_id: str, request_code: str = "",
                   run_id: str = "") -> tuple[str, int | None]:
    """根据申请单当前状态决定从哪一步续跑。返回 (step_id, status)。"""
    record = None
    if request_code:
        record = get_purchase_request(applicant_session, request_code, department_id)
    if record is None and run_id:
        record = find_latest_request(applicant_session, department_id, prefix=run_id)
    if record is None:
        return "S01", None
    status = int(record.get("status") or 0)
    if status == 9:
        return "DONE", status
    step = STATUS_TO_STEP.get(status, "S01")
    return step, status


def run_chain(sessions: dict, ctx: dict | None = None, run_id: str = "",
              start_from: str = "S01", retries: int = 1,
              resume: bool = False) -> ChainResult:
    """执行全链/续跑。ctx 可包含 request_code/project_name 等断点信息。"""
    ctx = dict(ctx or {})
    run_id = run_id or ctx.get("run_id") or new_run_id()
    ctx["run_id"] = run_id
    ctx.setdefault("project_name", f"{run_id}-全链")
    ctx.setdefault("survey_end_minutes", 1.5)
    reporter = Reporter(run_id)
    steps = build_steps(sessions)

    if resume:
        resolved, status = resolve_resume(
            sessions["applicant"], ctx["department_id"],
            request_code=ctx.get("request_code", ""), run_id=run_id)
        print(f"[ORCH] 续跑解析：当前状态={status}，从 {resolved} 开始")
        if resolved == "DONE":
            reporter.stage("DONE", "已完成", "success")
            path = reporter.finish("success")
            return ChainResult(run_id, "success", [], str(path),
                               str(path.with_suffix(".html")), status)
        start_from = resolved

    ids = [s.step_id for s in steps]
    if start_from not in ids and start_from != "DONE":
        raise ValueError(f"未知起始步骤：{start_from}")
    start_index = 0 if start_from == "DONE" else ids.index(start_from)

    final_status = None
    error = ""
    for step in steps[start_index:]:
        attempt = 0
        while True:
            attempt += 1
            started = time.time()
            try:
                print(f"\n[ORCH] ▶ {step.step_id} {step.name}（第 {attempt} 次）")
                step.run(ctx)
                duration = int((time.time() - started) * 1000)
                reporter.stage(step.step_id, step.name, "success", duration)
                print(f"[ORCH] ✓ {step.step_id} OK（{duration/1000:.1f}s）")
                break
            except Exception as exc:  # noqa: BLE001 - 编排层统一记录失败
                duration = int((time.time() - started) * 1000)
                if attempt <= retries and step.retryable:
                    reporter.stage(step.step_id, step.name, "retrying", duration,
                                   error=str(exc)[:500], attempt=attempt)
                    print(f"[ORCH] ↻ {step.step_id} 失败，重试：{exc}")
                    time.sleep(3)
                    continue
                reporter.stage(step.step_id, step.name, "failed", duration,
                               error=str(exc)[:2000], attempt=attempt)
                error = f"{step.step_id} {step.name}: {exc}"
                print(f"[ORCH] ✗ {step.step_id} FAILED：{exc}")
                break
        if error:
            break

    if not error and ctx.get("request_code"):
        final_status = int((get_purchase_request(
            sessions["applicant"], ctx["request_code"], ctx["department_id"]) or {}
        ).get("status") or 0)
        if final_status != 9:
            error = f"全链结束但申请单状态为 {final_status}，期望 9"

    status = "success" if not error else "failed"
    reporter.stage("RESULT", "全链结果", status, final_status=final_status,
                   requestCode=ctx.get("request_code", ""), error=error)
    json_path = reporter.finish(status)
    html_path = json_path.with_suffix(".html")
    if error:
        print(f"\n[ORCH] 全链失败：{error}")
        print(f"[ORCH] 报告：{json_path} / {html_path}")
    else:
        print(f"\n[ORCH] 全链完成：status={final_status} 采购中")
        print(f"[ORCH] 报告：{json_path} / {html_path}")
    return ChainResult(run_id, status, reporter.stages, str(json_path),
                       str(html_path), final_status, error)
