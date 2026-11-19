"""运行报告：reports/{run_id}/report.json + report.html（含步骤耗时/错误）。"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PACKAGE_ROOT / "reports"

STATUS_LABEL = {
    "success": "成功",
    "failed": "失败",
    "retrying": "重试",
}


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
        self._write_html(payload, path.with_suffix(".html"))
        return path

    def _write_html(self, payload: dict, path: Path) -> None:
        rows = []
        total_ms = 0
        for stage in self.stages:
            duration = stage.get("durationMs") or 0
            total_ms += duration if stage.get("status") != "retrying" else 0
            label = STATUS_LABEL.get(stage.get("status"), stage.get("status"))
            extra = ""
            if stage.get("error"):
                extra = html.escape(str(stage["error"]))
            if stage.get("final_status") is not None:
                extra += f"<br/>申请单状态：{stage['final_status']}"
            if stage.get("requestCode"):
                extra += f"<br/>申请单号：{html.escape(stage['requestCode'])}"
            attrs = ""
            for key, value in (stage.get("error") and {"title": stage["error"]} or {}).items():
                attrs = f' {key}="{html.escape(str(value))}"'
            rows.append(
                "<tr>"
                f"<td>{html.escape(str(stage.get('id')))}</td>"
                f"<td>{html.escape(str(stage.get('name')))}</td>"
                f"<td class='{stage.get('status')}'>{html.escape(str(label))}</td>"
                f"<td>{duration/1000:.1f}s</td>"
                f"<td{attrs}>{extra}</td>"
                "</tr>"
            )
        doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<title>采购前置全链报告 - {html.escape(self.run_id)}</title>
<style>
body{{font-family:-apple-system,"Segoe UI",Arial,sans-serif;margin:24px;color:#222}}
h1{{font-size:20px}}
table{{border-collapse:collapse;width:100%;margin-top:12px}}
th,td{{border:1px solid #ddd;padding:6px 10px;font-size:13px;text-align:left;vertical-align:top}}
th{{background:#f5f7fa}}
.success{{color:#1a7f37;font-weight:600}}
.failed{{color:#c62828;font-weight:600}}
.retrying{{color:#b26a00;font-weight:600}}
.summary{{margin-top:12px;font-size:14px}}
</style></head><body>
<h1>采购前置全链运行报告</h1>
<div class="summary">
<b>runId：</b>{html.escape(self.run_id)}<br/>
<b>状态：</b><span class="{payload['status']}">{STATUS_LABEL.get(payload['status'], payload['status'])}</span><br/>
<b>开始：</b>{html.escape(payload['startAt'])}　<b>结束：</b>{html.escape(payload['endAt'])}<br/>
<b>总耗时：</b>{total_ms/1000:.1f}s
</div>
<table><thead><tr><th>步骤</th><th>名称</th><th>结果</th><th>耗时</th><th>备注</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
</body></html>"""
        path.write_text(doc, encoding="utf-8")


def safe_filename(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", text)[:120]
