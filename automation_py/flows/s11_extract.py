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
    payload = {
        "surveyProjectUuid": survey_uuid,
        "argumentMode": "OFFLINE",
        "extractMode": "MANUAL",
        "gatherTime": (now + datetime.timedelta(hours=2)).strftime(fmt),
        "gatherEndTime": (now + datetime.timedelta(hours=3)).strftime(fmt),
        "gatherPlace": "自动化测试会议室",
        "evaluateExpertNumber": 3,
        "leaderSelectMode": "MANUAL",
        "conditions": [{
            "specialtyCode": specialty_code,
            "specialtyName": major.get("name"),
            "expertCount": 3,
        }],
    }
    api.start_extract(payload)

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
    call_ids = mock.create_call_ids(project["projectId"])
    mapping = {}
    for item in call_ids:
        expert_id = item.get("expertId") or item.get("expertUuid")
        call_id = item.get("callid") or item.get("callId")
        if expert_id and call_id:
            mapping[expert_id] = call_id
    for expert_uuid in expert_uuids:
        call_id = mapping.get(expert_uuid)
        assert_true(bool(call_id), f"专家 {expert_uuid} 未生成 callid")
        mock.callback(expert_uuid, call_id, "1")
    print("[S11] 已模拟专家电话确认（keypress=1）")

    detail = wait_until(
        lambda: (lambda d: d if (d.get("argument") or {}).get("extractStatus") == 2 else None)(
            api.get_detail(survey_uuid)
        ),
        timeout_s=30,
        message="专家确认后 extractStatus 未变为 2",
    )
    print(f"[S11] 抽取完成，extractStatus={detail['argument']['extractStatus']} OK")
    ctx["expert_uuids"] = expert_uuids
    return ctx
