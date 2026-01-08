"""Unit tests for release gate service."""

from __future__ import annotations

import json
from pathlib import Path

from src.release.gate import ReleaseGateService


def _write_template(path: Path) -> None:
    content = "\n".join(
        [
            "# Release Checklist",
            "",
            "- [ ] Risk review",
            "- [ ] Smoke tests",
        ]
    )
    path.write_text(content + "\n", encoding="utf-8")


def test_release_gate_prepare_and_record(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    template_path = tmp_path / "release_checklist.md"
    _write_template(template_path)

    service = ReleaseGateService(
        base_dir=tmp_path / "release",
        template_path=template_path,
        guardrails_metrics_path=tmp_path / "guardrails.jsonl",
    )
    checklist = service.prepare(version="v1.2.3")

    assert (tmp_path / "release" / "v1.2.3.md").exists()
    assert (tmp_path / "release" / "v1.2.3.json").exists()
    assert {task.task_id for task in checklist.tasks} == {"risk_review", "smoke_tests"}

    updated = service.record_result(
        version="v1.2.3",
        task_id="risk_review",
        status="pass",
        evidence_path="reports/validation_log/risk_review.md",
    )
    risk_task = next(task for task in updated.tasks if task.task_id == "risk_review")
    assert risk_task.status == "pass"


def test_release_gate_verify_emits_guardrails_block(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    template_path = tmp_path / "release_checklist.md"
    _write_template(template_path)
    metrics_path = tmp_path / "guardrails.jsonl"

    service = ReleaseGateService(
        base_dir=tmp_path / "release",
        template_path=template_path,
        guardrails_metrics_path=metrics_path,
    )
    service.prepare(version="v0.1.0")

    payload = service.verify_completion(version="v0.1.0")
    assert payload["status"] == "blocked"

    lines = metrics_path.read_text(encoding="utf-8").splitlines()
    guardrail = json.loads(lines[-1])
    assert guardrail["reason"] == "release_blocked"
    assert guardrail["auto_execute_forced_off"] is True
