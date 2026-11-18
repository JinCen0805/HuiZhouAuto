"""调研论证接口：规划抽取、手动勾选、指定组长、线下论证结果。"""
from __future__ import annotations

ARGUMENT_PREFIX = "/HospitalProcurement/hpSurveyProject/hpSurveyArgument"


class ArgumentApi:
    def __init__(self, session):
        self.session = session

    def list_majors(self, name: str = "") -> list[dict]:
        body = self.session.get(
            f"{ARGUMENT_PREFIX}/listMajors?name={name}", headers={"Accept": "application/json"}
        ).json() or {}
        if not body.get("success"):
            raise RuntimeError(f"专业目录查询失败：{str(body)[:300]}")
        return (body.get("data") or {}).get("majors") or []

    def get_detail(self, survey_uuid: str) -> dict:
        resp = self.session.get(f"{ARGUMENT_PREFIX}/getDetail?uuid={survey_uuid}")
        body = resp.json() or {}
        if not body.get("success"):
            raise RuntimeError(f"论证详情查询失败：{str(body)[:300]}")
        return body.get("data") or {}

    def start_extract(self, payload: dict) -> dict:
        resp = self.session.post(f"{ARGUMENT_PREFIX}/startExtract", json=payload)
        body = resp.json() or {}
        if not body.get("success"):
            raise RuntimeError(f"规划抽取失败：{str(body)[:500]}")
        return body

    def list_manual_candidates(self, survey_uuid: str, specialty_code: str,
                               current: int = 1, size: int = 20) -> list[dict]:
        body = self.session.get(
            f"{ARGUMENT_PREFIX}/listManualCandidates?uuid={survey_uuid}"
            f"&specialtyCode={specialty_code}&expertName=&current={current}&size={size}"
        ).json() or {}
        if not body.get("success"):
            raise RuntimeError(f"手动候选查询失败：{str(body)[:300]}")
        return (body.get("data") or {}).get("candidates") or []

    def save_manual_experts(self, survey_uuid: str, specialty_code: str,
                            expert_uuids: list[str]) -> dict:
        resp = self.session.post(
            f"{ARGUMENT_PREFIX}/saveManualExperts",
            json={
                "surveyProjectUuid": survey_uuid,
                "specialtyCode": specialty_code,
                "expertUuids": expert_uuids,
            },
        )
        body = resp.json() or {}
        if not body.get("success"):
            raise RuntimeError(f"保存勾选专家失败：{str(body)[:500]}")
        return body

    def designate_leader(self, survey_uuid: str, expert_uuid: str) -> dict:
        resp = self.session.post(
            f"{ARGUMENT_PREFIX}/designateLeader",
            json={"surveyProjectUuid": survey_uuid, "expertUuid": expert_uuid},
        )
        body = resp.json() or {}
        if not body.get("success"):
            raise RuntimeError(f"指定组长失败：{str(body)[:300]}")
        return body

    def save_offline_result(self, survey_uuid: str, result_attachment_ids: str,
                            submit: bool, other_attachment_ids: str = "") -> dict:
        resp = self.session.post(
            f"{ARGUMENT_PREFIX}/saveOfflineResult",
            json={
                "surveyProjectUuid": survey_uuid,
                "submit": submit,
                "resultAttachmentIds": result_attachment_ids,
                "otherAttachmentIds": other_attachment_ids,
            },
        )
        body = resp.json() or {}
        if not body.get("success"):
            raise RuntimeError(f"保存论证结果失败：{str(body)[:500]}")
        return body
