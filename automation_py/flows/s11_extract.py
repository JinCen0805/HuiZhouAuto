"""S11 专家抽取（线下 + 手动抽选 + mock 电话确认）。

注意：本地栈默认隔离了 HP→professor 的抽取建项 MQ 通道
（professor `draw.integration.listener.enabled=false`、vhost 隔离），
因此本流程在本地默认环境会卡在“professor 未建项”。
需先按 WP5 报告开启本地 MQ 桥接（或使用测试环境）后再运行。
"""
from __future__ import annotations

import datetime

from api.argument_api import ArgumentApi
from api.professor_mock import ProfessorMockApi
from core.assert_helper import assert_true
from flows.common import wait_until


def s11_extract(session, ctx: dict) -> dict:
    """规划抽取（线下/手动）→ 勾选 3 名专家 → mock 电话确认 → extractStatus=2。"""
    api = ArgumentApi(session)
    mock = ProfessorMockApi(session)
    survey_uuid = ctx["survey_project_uuid"]

    majors = api.list_majors()
    usable = [m for m in majors if int(m.get("expertCount") or 0) >= 3]
    assert_true(bool(usable), "专业目录里没有专家数 >=3 的专业")
    major = next((m for m in usable if m.get("code") == "A01"), usable[0])
    specialty_code = major["code"]
    print(f"[S11] 专业：{major.get('name')}（{specialty_code}），可用专家 {major.get('expertCount')}")

    now = datetime.datetime.now()
    fmt = "%Y-%m-%d %H:%M:%S"
    gather_start = now + datetime.timedelta(minutes=2)
    payload = {
        "surveyProjectUuid": survey_uuid,
        "argumentMode": "OFFLINE",
        "extractMode": "MANUAL",
        "gatherTime": gather_start.strftime(fmt),
        "gatherEndTime": (gather_start + datetime.timedelta(hours=2)).strftime(fmt),
        "gatherPlace": "自动化测试会议室",
        "evaluateExpertNumber": 3,
        "leaderSelectMode": "MANUAL",
        "conditions": [{
            "specialtyCode": specialty_code,
            "specialtyName": major.get("name"),
            "expertCount": 3,
        }],
    }
    ctx["gather_time"] = gather_start.strftime(fmt)
    api.start_extract(payload)

    # 本地环境：HP 定时任务被本地栈关闭，outbox relay 不执行，需要本地桥接；
    # 线上环境由真实 relay/MQ 完成，禁止使用本地桥接。
    is_local = bool(getattr(getattr(session, "cfg", None), "is_local", False))
    if is_local:
        try:
            from scripts.local_draw_bridge import publish_pending

            bridged = publish_pending()
            if bridged:
                print(f"[S11] 本地 MQ 桥接：已投递 {bridged} 条建项消息")
        except Exception as exc:  # noqa: BLE001 - 本地 docker 不可用时跳过
            print(f"[S11] 本地 MQ 桥接跳过：{exc}")

    # 等 professor 建项（本地默认隔离时此处会超时，抛出明确环境错误）
    section_code = f"HP-SURVEY-{survey_uuid}"
    project = wait_until(
        lambda: mock.find_project(section_code),
        timeout_s=60,
        message=(f"professor 未创建抽取项目（{section_code}）。本地栈默认关闭了 HP→professor "
                 f"抽取建项 MQ 通道，请先开启 MQ 桥接或使用测试环境"),
    )
    print(f"[S11] professor 抽取项目已创建：{project.get('projectId')}")

    # 勾选专家（等抽取值可查）
    candidates = wait_until(
        lambda: (lambda rows: rows if rows else None)(
            api.list_manual_candidates(survey_uuid, specialty_code)
        ),
        timeout_s=30,
        message="手动抽选候选为空（抽取项目尚未就绪）",
    )
    expert_uuids = []
    for candidate in candidates[:3]:
        uuid = candidate.get("expertUuid") or candidate.get("uuid")
        if uuid:
            expert_uuids.append(uuid)
    assert_true(len(expert_uuids) == 3, f"可用候选不足 3 人：{expert_uuids}")
    api.save_manual_experts(survey_uuid, specialty_code, expert_uuids)
    print(f"[S11] 已勾选专家：{expert_uuids}")

    # mock 电话确认（keypress=1 = 参加）
    # 仅本地环境需要补齐 professor 回传事件的队列绑定
    if is_local:
        try:
            from scripts.local_draw_bridge import ensure_result_bindings

            ensure_result_bindings()
        except Exception as exc:  # noqa: BLE001 - 本地 docker 不可用时跳过
            print(f"[S11] 结果绑定补齐跳过：{exc}")

    # callid 以 drawProjectExpertId 为键；需用项目详情把 expertId 映射过去
    call_ids = wait_until(
        lambda: (lambda rows: rows if rows else None)(mock.create_call_ids(project["projectId"])),
        timeout_s=30,
        message="professor 未生成 callid（专家可能尚未就绪）",
    )
    call_map = {
        item.get("drawProjectExpertId"): item.get("callid")
        for item in call_ids
        if item.get("drawProjectExpertId") and item.get("callid")
    }
    detail = mock.project_detail(project["projectId"])
    expert_records = {
        row.get("expertId"): row
        for row in detail.get("experts") or []
        if row.get("expertId")
    }
    for expert_uuid in expert_uuids:
        record = expert_records.get(expert_uuid)
        if not record:
            raise AssertionError(f"professor 项目详情未找到专家 {expert_uuid}")
        record_id = record.get("drawProjectExpertId")
        call_id = call_map.get(record_id)
        assert_true(bool(call_id), f"专家 {expert_uuid} 未生成 callid；映射={call_map}")
        mock.callback(record_id, call_id, "1")
    print("[S11] 已模拟专家电话确认（keypress=1）")

    def _extract_done():
        try:
            # 触发 HP 从 Dubbo 同步专家状态
            api.list_manual_candidates(survey_uuid, specialty_code)
        except Exception:  # noqa: BLE001 - 抽取完成后该接口可能返回不同结构，忽略
            pass
        current = api.get_detail(survey_uuid)
        return current if (current.get("argument") or {}).get("extractStatus") == 2 else None

    detail = wait_until(
        _extract_done,
        timeout_s=30,
        message="专家确认后 extractStatus 未变为 2",
    )
    print(f"[S11] 抽取完成，extractStatus={detail['argument']['extractStatus']} OK")
    ctx["expert_uuids"] = expert_uuids
    return ctx
