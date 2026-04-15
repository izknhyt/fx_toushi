"""Research promotion CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.ops.evidence import OpsEvidenceStore
from src.research.promotion import PromotionChecklistService

__all__ = ["promote", "checklist_show", "checklist_approve", "simulate"]


def promote(
    *,
    strategy_id: str,
    target_stage: str,
    actor: str | None,
    note: str | None = None,
    attachments: list[Path] | None = None,
    dry_run: bool = False,
    override: bool = False,
    idea_root: Path = Path("research") / "ideas",
    validation_playbook_dir: Path = Path("docs") / "validation_playbook",
    checklist_dir: Path = Path("reports") / "research" / "promotion" / "checklists",
    audit_log: Path = Path("logs") / "audit" / "promotion_gate.jsonl",
    metrics_path: Path = Path("metrics") / "promotion_gate.jsonl",
    agenda_event_log: Path = Path("logs") / "events" / "ops.agenda.jsonl",
    evidence_ledger: Path = Path("metrics") / "ops_evidence.jsonl",
    ops_worklog_path: Path = Path("ops_worklog.jsonl"),
    evidence_playbook_dir: Path = Path("docs") / "validation_playbook",
) -> Mapping[str, Any]:
    evidence_store = OpsEvidenceStore(
        ledger_path=evidence_ledger,
        playbook_dir=evidence_playbook_dir,
        ops_worklog_path=ops_worklog_path,
    )
    service = PromotionChecklistService(
        idea_root=idea_root,
        validation_playbook_dir=validation_playbook_dir,
        checklist_dir=checklist_dir,
        audit_log=audit_log,
        metrics_path=metrics_path,
        agenda_event_log=agenda_event_log,
        evidence_store=evidence_store,
    )
    receipt = service.promote(
        strategy_id=strategy_id,
        target_stage=target_stage,
        actor=actor,
        dry_run=dry_run,
        override=override,
    )
    return {
        "schema_version": "promotion.receipt.v1",
        "status": receipt.status,
        "result": receipt.to_dict(),
        "note": note,
        "attachments": [str(path) for path in attachments or []],
        "dry_run": dry_run,
    }


def checklist_show(
    *,
    strategy_id: str,
    target_stage: str,
    missing_only: bool,
    include_evidence: bool,
    idea_root: Path = Path("research") / "ideas",
    validation_playbook_dir: Path = Path("docs") / "validation_playbook",
    checklist_dir: Path = Path("reports") / "research" / "promotion" / "checklists",
) -> Mapping[str, Any]:
    service = PromotionChecklistService(
        idea_root=idea_root,
        validation_playbook_dir=validation_playbook_dir,
        checklist_dir=checklist_dir,
    )
    checklist = service.load(strategy_id, target_stage)
    result = service.evaluate(checklist)
    payload = checklist.to_dict()
    items = payload.get("items") or []
    filtered = []
    for item in items:
        if missing_only and item.get("status") == "pass":
            continue
        if not include_evidence:
            item = dict(item)
            item["evidence_refs"] = []
        filtered.append(item)
    payload["items"] = filtered
    return {
        "schema_version": "promotion.checklist.v1",
        "status": result.status,
        "result": result.to_dict(),
        "checklist": payload,
    }


def checklist_approve(
    *,
    strategy_id: str,
    target_stage: str,
    item_id: str,
    reviewer: str,
    note: str | None,
    runbook_step: str | None,
    attachments: list[Path],
    idea_root: Path = Path("research") / "ideas",
    validation_playbook_dir: Path = Path("docs") / "validation_playbook",
    checklist_dir: Path = Path("reports") / "research" / "promotion" / "checklists",
    audit_log: Path = Path("logs") / "audit" / "promotion_gate.jsonl",
    roles_path: Path = Path("config") / "roles.yaml",
    evidence_ledger: Path = Path("metrics") / "ops_evidence.jsonl",
    ops_worklog_path: Path = Path("ops_worklog.jsonl"),
    evidence_playbook_dir: Path = Path("docs") / "validation_playbook",
) -> Mapping[str, Any]:
    evidence_store = OpsEvidenceStore(
        ledger_path=evidence_ledger,
        playbook_dir=evidence_playbook_dir,
        ops_worklog_path=ops_worklog_path,
    )
    service = PromotionChecklistService(
        idea_root=idea_root,
        validation_playbook_dir=validation_playbook_dir,
        checklist_dir=checklist_dir,
        audit_log=audit_log,
        roles_path=roles_path,
        evidence_store=evidence_store,
    )
    note_text = note
    if runbook_step:
        suffix = f"runbook_step={runbook_step}"
        note_text = f"{note_text} ({suffix})" if note_text else suffix
    checklist = service.record_manual_review(
        strategy_id=strategy_id,
        target_stage=target_stage,
        item_id=item_id,
        reviewer=reviewer,
        note=note_text,
        evidence=attachments,
    )
    result = service.evaluate(checklist)
    return {
        "schema_version": "promotion.checklist.v1",
        "status": result.status,
        "result": result.to_dict(),
        "checklist": checklist.to_dict(),
    }


def simulate(
    *,
    strategy_id: str,
    target_stage: str,
    scenario: str,
    pending_evidence: list[Path],
    idea_root: Path = Path("research") / "ideas",
    validation_playbook_dir: Path = Path("docs") / "validation_playbook",
    checklist_dir: Path = Path("reports") / "research" / "promotion" / "checklists",
) -> Mapping[str, Any]:
    service = PromotionChecklistService(
        idea_root=idea_root,
        validation_playbook_dir=validation_playbook_dir,
        checklist_dir=checklist_dir,
    )
    checklist = service.load(strategy_id, target_stage)
    result = service.evaluate(checklist)
    return {
        "schema_version": "promotion.simulation.v1",
        "status": result.status,
        "scenario": scenario,
        "pending_evidence": [str(path) for path in pending_evidence],
        "result": result.to_dict(),
        "checklist": checklist.to_dict(),
    }
