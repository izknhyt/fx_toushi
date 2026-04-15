from __future__ import annotations

from pathlib import Path

import pytest

from src.ops.postmortem import IncidentClosureError, IncidentPostmortemService


def _build_service(tmp_path: Path) -> IncidentPostmortemService:
    template_path = tmp_path / "docs" / "templates" / "postmortem.md"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(
        "\n".join(
            [
                "# Postmortem {{incident_id}}",
                "{{#timeline}}",
                "| {{ts}} | {{runbook_ref}} | {{note}} | {{evidence}} |",
                "{{/timeline}}",
                "{{#follow_ups}}",
                "| {{task_id}} | {{status}} |",
                "{{/follow_ups}}",
                "Verified: {{verified_by}}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return IncidentPostmortemService(
        report_dir=tmp_path / "reports" / "ops" / "incidents",
        log_path=tmp_path / "logs" / "ops" / "incidents.jsonl",
        template_path=template_path,
        audit_dir=tmp_path / "logs" / "audit",
        metrics_path=tmp_path / "metrics" / "incident_postmortem.jsonl",
        validation_playbook_path=tmp_path / "docs" / "validation_playbook" / "AC43_postmortem.yaml",
    )


def test_postmortem_open_and_timeline(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    record = service.open(category="data", severity="critical", detected_by="monitor")
    incident_dir = tmp_path / "reports" / "ops" / "incidents" / record.incident_id
    assert incident_dir.exists()
    assert (incident_dir / "postmortem.md").exists()
    assert (incident_dir / "timeline.md").exists()

    service.append_timeline(
        incident_id=record.incident_id,
        runbook_ref="RUN-DATA-05#1",
        note="manual CSV",
        evidence_paths=["evidence.md"],
        duration_min=5,
    )
    timeline = (incident_dir / "timeline.md").read_text(encoding="utf-8")
    assert "RUN-DATA-05#1" in timeline


def test_postmortem_follow_up_and_close(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    record = service.open(category="risk", severity="high")

    service.register_follow_up(
        incident_id=record.incident_id,
        description="check guardrail",
        owner="ops",
        due="2026-01-31",
    )
    with pytest.raises(IncidentClosureError):
        service.close(
            incident_id=record.incident_id,
            verification_note="pending",
            verified_by="ops",
        )

    service.update_follow_up_status(
        incident_id=record.incident_id,
        task_id=f"{record.incident_id}-FU-01",
        status="done",
    )
    record = service.close(
        incident_id=record.incident_id,
        verification_note="verified",
        verified_by="ops",
    )
    assert record.status == "closed"
    metrics_path = tmp_path / "metrics" / "incident_postmortem.jsonl"
    assert metrics_path.exists()
    playbook_path = tmp_path / "docs" / "validation_playbook" / "AC43_postmortem.yaml"
    assert record.incident_id in playbook_path.read_text(encoding="utf-8")
