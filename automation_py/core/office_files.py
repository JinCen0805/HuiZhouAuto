"""文件服务上传：采购方式等业务附件用。"""
from __future__ import annotations

import time

import requests

from core.config import Config

CFG = Config.load()


def file_upload_url() -> str:
    value = CFG.env("HP_FILE_UPLOAD_URL")
    if value:
        return value
    if CFG.is_local:
        return "http://127.0.0.1:7807/doFile/upload"
    return "http://172.16.29.216:7807/doFile/upload"


def upload_file(content: bytes, file_name: str, user_id: str,
                content_type: str = "application/octet-stream") -> str:
    files = {"file": (file_name or "upload.bin", content, content_type)}
    data = {"userId": user_id, "lastModifiedDate": str(int(time.time() * 1000))}
    resp = requests.post(file_upload_url(), files=files, data=data, timeout=60)
    body = resp.json() or {}
    file_id = (body.get("data") or {}).get("uploadFileId")
    if resp.status_code != 200 or not file_id:
        raise RuntimeError(f"上传文件失败：HTTP {resp.status_code} {resp.text[:300]}")
    return file_id
