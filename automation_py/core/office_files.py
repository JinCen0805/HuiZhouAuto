"""文件服务与 OnlyOffice 回调：本地内容填充用（下载/上传/更新文档）。

仅用于本地/测试环境；线上禁止伪造回调。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path

import requests

from core.config import Config

CFG = Config.load()


def file_download_base() -> str:
    value = CFG.env("HP_FILE_DOWNLOAD_BASE")
    if value:
        return value
    if CFG.is_local:
        return "http://127.0.0.1:17707/doFile/download/?attachmentId="
    return "http://172.16.29.216:7707/doFile/download/?attachmentId="


def file_upload_url() -> str:
    value = CFG.env("HP_FILE_UPLOAD_URL")
    if value:
        return value
    if CFG.is_local:
        return "http://127.0.0.1:7807/doFile/upload"
    return "http://172.16.29.216:7807/doFile/upload"


def download_file(file_id: str) -> bytes:
    resp = requests.get(file_download_base() + file_id, timeout=60)
    if resp.status_code != 200 or not resp.content:
        raise RuntimeError(f"下载文件失败：fileId={file_id} HTTP {resp.status_code}")
    return resp.content


def upload_docx(content: bytes, file_name: str, user_id: str) -> str:
    files = {"file": (file_name or "upload.docx", content,
                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"userId": user_id, "lastModifiedDate": str(int(time.time() * 1000))}
    resp = requests.post(file_upload_url(), files=files, data=data, timeout=60)
    body = resp.json() or {}
    file_id = (body.get("data") or {}).get("uploadFileId")
    if resp.status_code != 200 or not file_id:
        raise RuntimeError(f"上传文件失败：HTTP {resp.status_code} {resp.text[:300]}")
    return file_id


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _jwt(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    signing = ".".join([
        _b64(json.dumps(header, separators=(",", ":")).encode()),
        _b64(json.dumps(payload, separators=(",", ":")).encode()),
    ])
    sig = hmac.new(secret.encode(), signing.encode(), hashlib.sha256).digest()
    return signing + "." + _b64(sig)


def _jwt_secret() -> str:
    return CFG.env("HP_ONLYOFFICE_JWT_SECRET", "please-change-onlyoffice-jwt-secret")


def _assert_local() -> None:
    if not CFG.is_local:
        raise RuntimeError("线上环境禁止用文件回调更新文档")


def update_purchase_document(session, document_key: str, file_id: str) -> dict:
    """用上传后的文件更新采购文档（模拟 OnlyOffice status=2 回调）。"""
    _assert_local()
    url = file_download_base() + file_id
    payload = {"status": 2, "key": document_key, "url": url}
    payload["token"] = _jwt(payload, _jwt_secret())
    resp = session.api("/HospitalProcurement/purchase/document/onlyoffice/callback",
                       method="POST", json=payload)
    try:
        body = resp.json() or {}
    except ValueError:
        body = {}
    if resp.status_code != 200 or body.get("error") not in (0, None):
        raise RuntimeError(f"更新采购文档回调失败：{resp.status_code} {resp.text[:300]}")
    return body


def update_audit_report(session, report_id: str, report_version: int, file_id: str) -> dict:
    """用上传后的文件更新审计报告（模拟 OnlyOffice status=2 回调）。"""
    _assert_local()
    url = file_download_base() + file_id
    key = f"audit-report-{report_id}-v{report_version}"
    payload = {"status": 2, "key": key, "url": url}
    payload["token"] = _jwt(payload, _jwt_secret())
    resp = session.api("/jjjc/purchaseAudit/template/onlyoffice/callback",
                       method="POST", json=payload)
    try:
        body = resp.json() or {}
    except ValueError:
        body = {}
    if resp.status_code != 200 or body.get("error") not in (0, None):
        raise RuntimeError(f"更新审计报告回调失败：{resp.status_code} {resp.text[:300]}")
    return body
