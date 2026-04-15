from __future__ import annotations

import json
from pathlib import Path

from src.core import health
from src.ops.readiness import OpsReadinessService


def _write_config(path: Path, evidence_path: Path) -> None:
    content = "\n".join(
        [
            "version: 1",
            "weights:",
            "  backups: 1.0",
            "evidence_paths:",
            f"  backups: {evidence_path}",
            "thresholds:",
            "  min_score: 80",
            "  warn_score: 85",
            "runbook_refs:",
            "  review: OPS-READINESS-01",
        ]
    )
    path.write_text(content + "\n", encoding="utf-8")


def test_ops_readiness_metrics_and_alert(tmp_path: Path, monkeypatch: object) -> None:
    config_path = tmp_path / "ops_readiness.yaml"
    evidence_path = tmp_path / "missing.md"
    _write_config(config_path, evidence_path)

    events_path = tmp_path / "logs" / "events" / "health.changed.jsonl"
    monkeypatch.setattr(health, "DEFAULT_HEALTH_EVENT_LOG", events_path)

    service = OpsReadinessService(
        config_path=config_path,
        metrics_path=tmp_path / "ops_readiness.jsonl",
        max_age_days=1,
    )
    snapshot = service.evaluate()
    alerted = service.raise_alert(snapshot)
    service.record_metrics(snapshot, alerts_triggered=1 if alerted else 0)

    metrics_payloads = [
        json.loads(line)
        for line in (tmp_path / "ops_readiness.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert metrics_payloads[-1]["readiness_score"] == snapshot.result.score
    assert metrics_payloads[-1]["alerts_triggered"] == 1
    assert events_path.exists()
    assert "ops_readiness_low" in events_path.read_text(encoding="utf-8")


def test_ops_readiness_report(tmp_path: Path) -> None:
    config_path = tmp_path / "ops_readiness.yaml"
    evidence_path = tmp_path / "evidence.md"
    evidence_path.write_text("# evidence\n", encoding="utf-8")
    _write_config(config_path, evidence_path)

    service = OpsReadinessService(
        config_path=config_path,
        report_dir=tmp_path / "reports" / "ops" / "readiness",
        metrics_path=tmp_path / "ops_readiness.jsonl",
    )
    snapshot = service.evaluate()
    report_path = service.generate_report(snapshot, period="2025W01")
    assert report_path.exists()
