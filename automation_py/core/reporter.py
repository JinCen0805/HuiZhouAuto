"""运行报告：reports/{run_id}/report.json + screenshots 目录（WP8 完善）。"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PACKAGE_ROOT / "reports"


def new_run_id() -> str:
    """生成 runId：UI自动化-YYYYmmdd-HHMMSS-xxx（数据标记/清理用）。"""
    import random
    import string

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase, k=3))
    return f"UI自动化-{ts}-{suffix}"


class Reporter:
    def __init__(self, run_id: str | None = None):
        self.run_id = run_id or new_run_id()
        self.run_dir = REPORTS_DIR / self.run_id
        self.shots_dir = self.run_dir / "screenshots"
        self.shots_dir.mkdir(parents=True, exist_ok=True)
        self.stages: list[dict] = []
        self.started_at = datetime.now().isoformat(timespec="seconds")

    def stage(self, stage_id: str, name: str, status: str,
              duration_ms: int | None = None, **extra) -> None:
        self.stages.append({
            "id": stage_id,
            "name": name,
            "status": status,
            "durationMs": duration_ms,
            **extra,
        })

    def finish(self, status: str = "success") -> Path:
        payload = {
            "runId": self.run_id,
            "startAt": self.started_at,
            "endAt": datetime.now().isoformat(timespec="seconds"),
            "status": status,
            "stages": self.stages,
        }
        path = self.run_dir / "report.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return path


def safe_filename(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", text)[:120]
