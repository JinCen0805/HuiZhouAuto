"""S11 专家抽取：规划抽取 → 勾选专家 → 通知确认（手工拨号登记 / mock 电话确认）。

- 默认全 UI（``HP_EXTRACT_MODE=ui``）：调研论证列表 → 规划页 extract.html（线下论证 /
  手动抽选 / 通知方式）→ 勾选页 pick.html → 拨号登记页 manualDial.html，按人工口径逐页操作；
  ``HP_EXTRACT_MODE=api`` 走接口直调（线上旧前端可切回）。
- 通知方式默认 MANUAL（手工拨号，后端 2026-11-26 新增 dialMode）：登记齐抽取人数后
  extractStatus=2，不依赖 mock 电话回调和 professor 回传队列；``HP_DIAL_MODE=AUTO`` 或
  后端尚不支持（规划后 getDetail.dialMode 仍为 AUTO）时自动走 mock 回调路径。

本地栈默认隔离了 HP→professor 的抽取建项 MQ 通道，需本地 MQ 桥接（``local_draw_bridge``）。
"""
from __future__ import annotations

import datetime
import os

from api.argument_api import ArgumentApi
from api.professor_mock import ProfessorMockApi
from core import browser as browser_helpers
from core.assert_helper import assert_true
from flows.common import wait_until

EXPERT_COUNT = 3
GATHER_PLACE = "自动化测试会议室"


def _choose_condition(api: ArgumentApi, ctx: dict) -> dict:
    """选抽取条件：优先科室维度（可抽人数最多的科室），科室目录不可用时回落专业维度。"""
    majors = api.list_majors()
    # 2026-11-24 起院内专家按科室管理：科室目录带「含下级」可抽人数，优先按科室规划。
    try:
        departments = api.list_departments()
    except Exception as exc:  # noqa: BLE001 - 兼容未升级环境
        print(f"[S11] 科室目录不可用，回落到专业模式：{str(exc)[:120]}")
        departments = []
    usable_depts = [d for d in departments if int(d.get("expertCount") or 0) >= EXPERT_COUNT]
    usable_majors = [m for m in majors if int(m.get("expertCount") or 0) >= EXPERT_COUNT]
    assert_true(bool(usable_depts or usable_majors), "科室/专业目录里都没有可抽人数 >=3 的节点")
    if usable_depts:
        dimension = "department"
        # 取可抽人数最多的科室节点（人数已含下级科室），保证 3 人足够。
        node = max(usable_depts, key=lambda item: (int(item.get("expertCount") or 0),
                                                   str(item.get("id") or "")))
        key = str(node["id"])
        name = node.get("name") or key
        condition = {
            "departmentNodeId": key,
            "departmentName": name,
            "expertCount": EXPERT_COUNT,
            "isDrawLocal": "1",
            "expertType": "1",
        }
        print(f"[S11] 科室：{name}（{key}），可抽人数 {node.get('expertCount')}")
    else:
        dimension = "specialty"
        # 系统要求抽取条件必须带专业，不能传空。优先选人数足够的最上级专业，覆盖其下级专业。
        major = min(usable_majors, key=lambda item: (len(str(item.get("code") or "")),
                                                     str(item.get("code") or "")))
        key = major["code"]
        name = major.get("name") or key
        condition = {"specialtyCode": key, "specialtyName": name, "expertCount": EXPERT_COUNT}
        print(f"[S11] 专业：{name}（{key}），可用专家 {major.get('expertCount')}")
    ctx["argument_dimension"] = dimension
    ctx["argument_condition_key"] = key
    return {"dimension": dimension, "key": key, "name": name, "condition": condition}


def _mock_phone_confirm(mock: ProfessorMockApi, session, project: dict, expert_uuids: list[str],
                        is_local: bool) -> None:
    """语音自动通知：mock 电话确认（keypress=1 = 参加）。"""
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


def s11_extract(session, ctx: dict) -> dict:
    """规划抽取（线下/手动）→ 勾选 3 名专家 → 手工拨号登记（或 mock 电话确认）→ extractStatus=2。"""
    api = ArgumentApi(session)
    mock = ProfessorMockApi(session)
    survey_uuid = ctx.get("survey_project_uuid")
    if not survey_uuid:
        from api.survey_api import SurveyApi

        project = SurveyApi(session).find_project(ctx["project_name"])
        assert_true(project is not None, f"未找到调研项目：{ctx['project_name']}")
        survey_uuid = project["uuid"]
        ctx["survey_project_uuid"] = survey_uuid

    chosen = _choose_condition(api, ctx)
    dimension, condition_key, condition_name = chosen["dimension"], chosen["key"], chosen["name"]

    # 断点续跑：已抽齐直接跳过；已规划未抽齐则跳过规划，从勾选/登记继续
    argument = (api.get_detail(survey_uuid).get("argument") or {})
    if argument.get("extractStatus") == 2:
        print("[S11] 专家已抽取完成（extractStatus=2），跳过")
        ctx["dial_mode"] = str(argument.get("dialMode") or "").upper()
        return ctx
    already_planned = bool(argument.get("uuid"))
    if already_planned:
        print(f"[S11] 已有抽取规划（extractStatus={argument.get('extractStatus')}），跳过规划")

    # 执行方式：默认全 UI；HP_EXTRACT_MODE=api 走接口直调
    extract_mode = str(ctx.get("extract_mode") or os.environ.get("HP_EXTRACT_MODE") or "ui").lower()
    assert_true(extract_mode in ("ui", "api"), f"HP_EXTRACT_MODE 只支持 ui/api：{extract_mode}")
    # 通知方式：默认手工拨号（登记参与，不走语音外呼/mock 回调）；HP_DIAL_MODE=AUTO 可回落
    dial_mode_cfg = str(ctx.get("dial_mode") or os.environ.get("HP_DIAL_MODE") or "MANUAL").upper()
    assert_true(dial_mode_cfg in ("MANUAL", "AUTO"), f"HP_DIAL_MODE 只支持 MANUAL/AUTO：{dial_mode_cfg}")

    fmt = "%Y-%m-%d %H:%M:%S"
    gather_start = datetime.datetime.now() + datetime.timedelta(minutes=2)
    ctx["gather_time"] = gather_start.strftime(fmt)

    # 本地环境：HP 定时任务被本地栈关闭，outbox relay 不执行，需要本地桥接；
    # 线上环境由真实 relay/MQ 完成，禁止使用本地桥接。
    is_local = bool(getattr(getattr(session, "cfg", None), "is_local", False))
    page = None

    # ── 1. 规划抽取 ────────────────────────────────────────────
    if extract_mode == "ui":
        from pages.survey_argument import SurveyArgumentPage
        from pages.survey_extract import SurveyExtractPage

        list_page = SurveyArgumentPage(session)
        list_page.search(ctx["project_name"])
        page = SurveyExtractPage(list_page, session)
        if not already_planned:
            frame = page.open_extract(ctx["project_name"])
            page.fill_plan(frame, dial_mode=dial_mode_cfg, gather_place=GATHER_PLACE,
                           expert_count=EXPERT_COUNT, condition_key=condition_key,
                           condition_name=condition_name)
            page.save_plan(frame)
            print(f"[S11] 规划已保存（UI）：线下论证 / 手动抽选 / 条件 {condition_name}")
    elif not already_planned:
        payload = {
            "surveyProjectUuid": survey_uuid,
            "argumentMode": "OFFLINE",
            "extractMode": "MANUAL",
            "dialMode": dial_mode_cfg,
            "gatherTime": gather_start.strftime(fmt),
            "gatherEndTime": (gather_start + datetime.timedelta(hours=2)).strftime(fmt),
            "gatherPlace": GATHER_PLACE,
            "evaluateExpertNumber": EXPERT_COUNT,
            "leaderSelectMode": "MANUAL",
            "conditions": [chosen["condition"]],
        }
        api.start_extract(payload)
        print("[S11] 规划已保存（接口）")

    # 以后端实际保存的通知方式为准：旧版后端不识别 dialMode 时仍为 AUTO，自动回落 mock 回调
    planned = api.get_detail(survey_uuid)
    planned_dial = planned.get("dialMode") or (planned.get("argument") or {}).get("dialMode") or "AUTO"
    dial_mode = str(planned_dial).upper()
    ctx["dial_mode"] = dial_mode
    print(f"[S11] 通知方式：{'手工拨号登记' if dial_mode == 'MANUAL' else '语音自动通知（mock 回调）'}")

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

    # ── 2. 勾选专家（名单已够则跳过；不足只补差额） ─────────────
    roster = [e for e in (api.get_detail(survey_uuid).get("experts") or []) if e.get("expertUuid")]
    need = max(0, EXPERT_COUNT - len(roster))
    if need == 0:
        expert_uuids = [e["expertUuid"] for e in roster[:EXPERT_COUNT]]
        print(f"[S11] 名单已有 {len(roster)} 人，跳过勾选：{expert_uuids}")
    elif extract_mode == "ui":
        if not any("surveyArgument/pick.html" in f.url for f in session.page.frames):
            page.open_pick(ctx["project_name"])
        pick_frame = browser_helpers.get_frame(session.page, "surveyArgument/pick.html")
        expert_uuids = [e["expertUuid"] for e in roster] + page.pick_experts(pick_frame, need)
        session.page.wait_for_timeout(1000)  # 等列表按弹窗 end 回调刷新
        print(f"[S11] 已勾选专家（UI 勾选页）：{expert_uuids}")
    else:
        candidates = wait_until(
            lambda: (lambda rows: rows if rows else None)(
                api.list_manual_candidates(survey_uuid, department_node_id=condition_key)
                if dimension == "department"
                else api.list_manual_candidates(survey_uuid, specialty_code=condition_key)
            ),
            timeout_s=30,
            message="手动抽选候选为空（抽取项目尚未就绪）",
        )
        fresh = []
        for candidate in candidates:
            uuid = candidate.get("expertUuid") or candidate.get("uuid")
            if uuid and uuid not in roster and not candidate.get("locked"):
                fresh.append(uuid)
            if len(fresh) >= need:
                break
        assert_true(len(fresh) >= need, f"可用候选不足 {need} 人：{fresh}")
        if dimension == "department":
            api.save_manual_experts(survey_uuid, fresh, department_node_id=condition_key)
        else:
            api.save_manual_experts(survey_uuid, fresh, specialty_code=condition_key)
        expert_uuids = [e["expertUuid"] for e in roster] + fresh
        print(f"[S11] 已勾选专家：{expert_uuids}")

    # ── 3. 通知确认 ────────────────────────────────────────────
    if dial_mode == "MANUAL":
        if extract_mode == "ui":
            dial_frame = page.dial_frame_or_open(ctx["project_name"])
            registered = page.register_all_agree(dial_frame)
            page.close_dial(dial_frame)
            browser_helpers.close_all_layers(session.page)
            print(f"[S11] 已在拨号登记页登记 {registered} 位专家为参与")
        else:
            argument_uuid = str((planned.get("argument") or {}).get("uuid") or "")
            if not argument_uuid:
                argument_uuid = str(((api.get_detail(survey_uuid).get("argument") or {}).get("uuid")) or "")
            assert_true(bool(argument_uuid), "论证详情缺少 argument.uuid，无法登记拨号结果")
            # drawStatus=2 为已确认；续跑时只登记尚未确认的人
            confirmed = {e.get("expertUuid") for e in (api.get_detail(survey_uuid).get("experts") or [])
                         if str(e.get("drawStatus") or "") == "2"}
            pending = [u for u in expert_uuids if u not in confirmed]
            for expert_uuid in pending:
                api.save_manual_dial_result(argument_uuid, expert_uuid, "AGREE")
            print(f"[S11] 已手工拨号登记 {len(pending)} 位专家为参与（AGREE）")
    else:
        _mock_phone_confirm(mock, session, project, expert_uuids, is_local)

    def _extract_done():
        try:
            # 触发 HP 从 Dubbo 同步专家状态
            if dimension == "department":
                api.list_manual_candidates(survey_uuid, department_node_id=condition_key)
            else:
                api.list_manual_candidates(survey_uuid, specialty_code=condition_key)
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
