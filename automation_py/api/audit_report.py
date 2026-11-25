"""本地测试辅助：用 JWT 伪造 OnlyOffice 回调，把审计报告标记为“已保存”。

生产环境由 OnlyOffice 编辑器保存触发真实回调；本地自动化不打开编辑器时，
用本函数按同一协议（HS256 JWT + 下载/回写）完成落库，避免依赖 UI。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import os

DEFAULT_SECRET = "please-change-onlyoffice-jwt-secret"

# 2026-11-24 起审计报告初稿在 HP 侧初始化/保存，回调也走 HP。
HP_CALLBACK_PATH = "/HospitalProcurement/hospitalPurchaseAudit/report/onlyoffice/callback"
HP_FILE_DOWNLOAD_BASE = "http://127.0.0.1:17707?attachmentId="


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _jwt(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join([
        _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ])
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"),
                         hashlib.sha256).digest()
    return signing_input + "." + _b64url(signature)


def save_hp_report_via_callback(session, audit_id: str, timeout_s: int = 30) -> dict:
    """把 HP 审计报告初稿标记为已保存（reportStatus=2）。返回 report detail。

    仅允许本地环境使用；线上必须由 OnlyOffice 编辑器真实保存，禁止伪造回调。
    """
    cfg = getattr(session, "cfg", None)
    if cfg is not None and not getattr(cfg, "is_local", False):
        raise RuntimeError("线上环境禁止伪造 OnlyOffice 回调保存审计报告")
    from api.document_api import audit_report_detail

    secret = os.getenv("HP_ONLYOFFICE_JWT_SECRET", DEFAULT_SECRET)
    detail = audit_report_detail(session, audit_id)
    report = detail.get("report") or {}
    if not report.get("reportId"):
        raise RuntimeError("审计报告尚未生成，无法保存")
    if int(report.get("reportStatus") or 0) == 2:
        return detail
    report_id = report.get("reportId")
    file_id = report.get("fileId")
    version = int(report.get("reportVersion") or 1)
    key = f"audit-report-{report_id}-v{version}"
    url = HP_FILE_DOWNLOAD_BASE + str(file_id)
    token = _jwt({"status": 2, "key": key, "url": url}, secret)
    body = {"status": 2, "key": key, "url": url, "token": token}
    resp = session.api(HP_CALLBACK_PATH, method="POST", json=body)
    if resp.status_code != 200:
        raise RuntimeError(f"OnlyOffice 回调失败：{resp.status_code} {resp.text[:300]}")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        detail = audit_report_detail(session, audit_id)
        report = detail.get("report") or {}
        if int(report.get("reportStatus") or 0) == 2:
            return detail
        time.sleep(1)
    raise TimeoutError("审计报告回调后未变为已保存状态")
