"""WP8 编排层单元测试：续跑解析 / 报告生成（不需要浏览器与业务环境）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.reporter import Reporter
from flows import orchestrator


class _FakeSession:
    pass


def test_resume_mapping_by_status(monkeypatch):
    for status, expected in (
        (22, "S04"), (8, "S05"), (7, "S06"), (4, "S10"),
        (15, "S15"), (20, "S17"), (19, "S18"), (18, "S18"),
        (10, "S19"), (11, "S20"), (9, "DONE"),
    ):
        monkeypatch.setattr(orchestrator, "get_purchase_request",
                            lambda *a, _s=status, **k: {"status": _s})
        step, resolved = orchestrator.resolve_resume(
            _FakeSession(), "dept", request_code="X")
        assert step == expected, f"status={status} 应续跑到 {expected}，实际 {step}"
        assert resolved == status


def test_resume_unknown_status_starts_from_s01(monkeypatch):
    monkeypatch.setattr(orchestrator, "get_purchase_request",
                        lambda *a, **k: {"status": 0})
    step, status = orchestrator.resolve_resume(_FakeSession(), "dept", request_code="X")
    assert step == "S01"
    assert status == 0


def test_run_chain_success_and_report(monkeypatch, tmp_path):
    calls = []
    fake_steps = [
        orchestrator.Step("S01", "创建申请", lambda ctx: calls.append("S01")),
        orchestrator.Step("S02", "后续步骤", lambda ctx: calls.append("S02")),
    ]
    monkeypatch.setattr(orchestrator, "build_steps", lambda sessions: fake_steps)
    monkeypatch.setattr(orchestrator, "get_purchase_request",
                        lambda *a, **k: {"status": 9})
    monkeypatch.setattr(orchestrator.Reporter, "__init__",
                        lambda self, run_id=None: _init_reporter(self, tmp_path))

    result = orchestrator.run_chain(
        {"applicant": _FakeSession()},
        ctx={"department_id": "dept", "request_code": "X"},
        run_id="UI自动化-test", start_from="S01", retries=0,
    )
    assert result.status == "success"
    assert result.final_status == 9
    assert calls == ["S01", "S02"]
    payload = json.loads(Path(result.report_json).read_text(encoding="utf-8"))
    assert payload["status"] == "success"
    assert [s["id"] for s in payload["stages"]][-1] == "RESULT"
    assert Path(result.report_html).exists()


def _init_reporter(self, tmp_path):
    import core.reporter as reporter_mod

    self.run_id = "UI自动化-test"
    self.run_dir = tmp_path / "run"
    self.run_dir.mkdir(parents=True, exist_ok=True)
    self.stages = []
    self.started_at = "2026-01-01T00:00:00"


def test_run_chain_retries_then_fails(monkeypatch, tmp_path):
    attempts = {"n": 0}

    def flaky(ctx):
        attempts["n"] += 1
        raise RuntimeError("模拟失败")

    fake_steps = [orchestrator.Step("S01", "创建申请", flaky, retryable=True)]
    monkeypatch.setattr(orchestrator, "build_steps", lambda sessions: fake_steps)
    monkeypatch.setattr(orchestrator.Reporter, "__init__",
                        lambda self, run_id=None: _init_reporter(self, tmp_path))

    result = orchestrator.run_chain(
        {"applicant": _FakeSession()},
        ctx={"department_id": "dept"},
        run_id="UI自动化-test", start_from="S01", retries=1,
    )
    assert result.status == "failed"
    assert attempts["n"] == 2
    assert "模拟失败" in result.error


def test_reporter_writes_html(tmp_path):
    reporter = Reporter("UI自动化-unit")
    reporter.run_dir = tmp_path / "run"
    reporter.run_dir.mkdir(parents=True, exist_ok=True)
    reporter.stage("S01", "创建申请", "success", 1200)
    reporter.stage("S02", "后续", "failed", 500, error="boom")
    path = reporter.finish("failed")
    html = path.with_suffix(".html").read_text(encoding="utf-8")
    assert "采购前置全链运行报告" in html
    assert "boom" in html
    assert "失败" in html
