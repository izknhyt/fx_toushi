from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ops.degradation import DegradationPlaybookError, DegradationPlaybookOrchestrator


def _make_orchestrator(tmp_path: Path) -> DegradationPlaybookOrchestrator:
    return DegradationPlaybookOrchestrator(
        playbook_dir=tmp_path / "reports" / "ops" / "degradation_playbooks",
        event_log=tmp_path / "logs" / "events" / "degradation.jsonl",
        shadow_event_log=tmp_path / "logs" / "events" / "shadow.jsonl",
        audit_log=tmp_path / "logs" / "audit" / "degradation.jsonl",
        metrics_path=tmp_path / "metrics" / "degradation_playbook.jsonl",
        validation_playbook_path=tmp_path / "docs" / "validation_playbook" / "AC34_degradation.yaml",
        evidence_ledger=tmp_path / "logs" / "audit" / "evidence.jsonl",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
    )


def test_degradation_flow(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator(tmp_path)
    instance = orchestrator.start("data_latency", severity="high", reason="lag")
    assert instance.status == "in_progress"

    evidence = tmp_path / "evidence.md"
    evidence.write_text("ok\n", encoding="utf-8")
    for node in instance.nodes:
        instance = orchestrator.ack(
            instance.instance_id,
            node_id=node.node_id,
            evidence_path=evidence,
            actor="user:ops",
        )
    assert instance.status == "ready_for_recovery"

    report = tmp_path / "report.md"
    report.write_text("recovered\n", encoding="utf-8")
    recovered = orchestrator.recover(instance.instance_id, attach_report=report)
    assert recovered.status == "completed"
    playbook = (
        tmp_path / "docs" / "validation_playbook" / "AC34_degradation.yaml"
    ).read_text(encoding="utf-8")
    assert "instance_id" in playbook


def test_degradation_requires_evidence(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator(tmp_path)
    instance = orchestrator.start("data_latency", severity="high", reason="lag")
    with pytest.raises(DegradationPlaybookError):
        orchestrator.ack(instance.instance_id, node_id=instance.nodes[0].node_id, evidence_path=None, actor="ops")


def test_degradation_status_round_trip(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator(tmp_path)
    instance = orchestrator.start("rate_limit", severity="medium", reason=None)
    loaded = orchestrator.status(instance.instance_id)
    payload = json.loads(
        (tmp_path / "reports" / "ops" / "degradation_playbooks" / f"{instance.instance_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert loaded.instance_id == payload["instance_id"]
