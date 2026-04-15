"""Degradation playbook CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.ops.degradation import DegradationPlaybookError, DegradationPlaybookOrchestrator


def trigger(
    *,
    scenario: str,
    severity: str,
    reason: str | None,
    dry_run: bool,
    playbook_dir: Path,
    event_log: Path,
    shadow_event_log: Path,
    audit_log: Path,
    metrics_path: Path,
    validation_playbook_path: Path,
    evidence_ledger: Path,
    ops_worklog_path: Path,
) -> Mapping[str, Any]:
    orchestrator = DegradationPlaybookOrchestrator(
        playbook_dir=playbook_dir,
        event_log=event_log,
        shadow_event_log=shadow_event_log,
        audit_log=audit_log,
        metrics_path=metrics_path,
        validation_playbook_path=validation_playbook_path,
        evidence_ledger=evidence_ledger,
        ops_worklog_path=ops_worklog_path,
    )
    instance = orchestrator.start(
        scenario,
        severity=severity,
        reason=reason,
        dry_run=dry_run,
    )
    return {"status": "ok", "instance": instance.to_dict()}


def status(
    *,
    instance_id: str,
    playbook_dir: Path,
) -> Mapping[str, Any]:
    orchestrator = DegradationPlaybookOrchestrator(playbook_dir=playbook_dir)
    instance = orchestrator.status(instance_id)
    return {"status": "ok", "instance": instance.to_dict()}


def ack(
    *,
    instance_id: str,
    node_id: str,
    evidence_path: Path | None,
    actor: str | None,
    note: str | None,
    handoff: str | None,
    playbook_dir: Path,
    event_log: Path,
    shadow_event_log: Path,
    audit_log: Path,
    metrics_path: Path,
    validation_playbook_path: Path,
    evidence_ledger: Path,
    ops_worklog_path: Path,
) -> Mapping[str, Any]:
    orchestrator = DegradationPlaybookOrchestrator(
        playbook_dir=playbook_dir,
        event_log=event_log,
        shadow_event_log=shadow_event_log,
        audit_log=audit_log,
        metrics_path=metrics_path,
        validation_playbook_path=validation_playbook_path,
        evidence_ledger=evidence_ledger,
        ops_worklog_path=ops_worklog_path,
    )
    instance = orchestrator.ack(
        instance_id,
        node_id=node_id,
        evidence_path=evidence_path,
        actor=actor,
        note=note,
        handoff=handoff,
    )
    return {"status": "ok", "instance": instance.to_dict()}


def recover(
    *,
    instance_id: str,
    attach_report: Path | None,
    playbook_dir: Path,
    event_log: Path,
    shadow_event_log: Path,
    audit_log: Path,
    metrics_path: Path,
    validation_playbook_path: Path,
    evidence_ledger: Path,
    ops_worklog_path: Path,
) -> Mapping[str, Any]:
    orchestrator = DegradationPlaybookOrchestrator(
        playbook_dir=playbook_dir,
        event_log=event_log,
        shadow_event_log=shadow_event_log,
        audit_log=audit_log,
        metrics_path=metrics_path,
        validation_playbook_path=validation_playbook_path,
        evidence_ledger=evidence_ledger,
        ops_worklog_path=ops_worklog_path,
    )
    instance = orchestrator.recover(instance_id, attach_report=attach_report)
    return {"status": "ok", "instance": instance.to_dict()}


__all__ = ["trigger", "status", "ack", "recover", "DegradationPlaybookError"]
