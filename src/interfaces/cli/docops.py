"""DocOps CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.docops.registry import DocRegistryError, DocValidationError, DocsRegistry
from src.docops.runbook_inventory import RunbookInventoryService
from src.ops.evidence import OpsEvidenceStore


def runbook_status(
    *,
    category: str | None = None,
    overdue_only: bool = False,
    include_evidence: bool = False,
    runbooks_dir: Path = Path("docs/runbooks"),
    governance_dir: Path = Path("reports/governance"),
    audit_dir: Path = Path("reports/audit"),
    templates_dir: Path = Path("docs/templates"),
    onboarding_path: Path = Path("docs/onboarding.md"),
    review_log_path: Path = Path("reports/governance/doc_review_log.jsonl"),
    inventory_path: Path = Path("reports/governance/runbook_inventory_status.json"),
    metrics_path: Path = Path("metrics/docops.jsonl"),
    event_log_path: Path = Path("logs/events/docops.jsonl"),
) -> Mapping[str, Any]:
    registry = DocsRegistry(
        runbooks_dir=runbooks_dir,
        governance_dir=governance_dir,
        audit_dir=audit_dir,
        templates_dir=templates_dir,
        onboarding_path=onboarding_path,
        review_log_path=review_log_path,
        event_log_path=event_log_path,
    )
    inventory = RunbookInventoryService(
        docs_registry=registry,
        inventory_path=inventory_path,
        metrics_path=metrics_path,
        event_log_path=event_log_path,
    ).refresh(no_write=True)
    runbooks = inventory.runbooks
    if category:
        runbooks = {
            key: value
            for key, value in runbooks.items()
            if value.get("category") == category
        }
    if overdue_only:
        runbooks = {
            key: value
            for key, value in runbooks.items()
            if value.get("status") in {"overdue", "grace"}
        }
    if not include_evidence:
        for entry in runbooks.values():
            entry.pop("evidence_path", None)
    return {
        "status": "ok",
        "runbooks": runbooks,
        "summary": inventory.summary,
    }


def runbook_review(
    *,
    runbook_id: str,
    notes: str,
    evidence: Path,
    performed_by: str,
    confidence_pct: float = 0.9,
    validation_playbook_id: str | None = None,
    runbooks_dir: Path = Path("docs/runbooks"),
    governance_dir: Path = Path("reports/governance"),
    audit_dir: Path = Path("reports/audit"),
    templates_dir: Path = Path("docs/templates"),
    onboarding_path: Path = Path("docs/onboarding.md"),
    review_log_path: Path = Path("reports/governance/doc_review_log.jsonl"),
    event_log_path: Path = Path("logs/events/docops.jsonl"),
    validation_dir: Path = Path("docs/validation_playbook"),
) -> Mapping[str, Any]:
    if validation_playbook_id:
        validation_path = validation_dir / f"{validation_playbook_id}_runbook.yaml"
        if not validation_path.exists():
            raise DocValidationError(f"validation playbook missing: {validation_path}")
        _append_validation_review(
            validation_path,
            runbook_id=runbook_id,
            evidence_path=evidence,
            notes=notes,
        )
    registry = DocsRegistry(
        runbooks_dir=runbooks_dir,
        governance_dir=governance_dir,
        audit_dir=audit_dir,
        templates_dir=templates_dir,
        onboarding_path=onboarding_path,
        review_log_path=review_log_path,
        event_log_path=event_log_path,
    )
    review = registry.record_review(
        document_id=runbook_id,
        performed_by=performed_by,
        notes=notes,
        evidence_path=evidence,
        confidence_pct=confidence_pct,
    )
    evidence_entry = OpsEvidenceStore().register(
        category="runbook",
        artifact=evidence,
        runbook_refs=[runbook_id],
        validation_playbook_id=validation_playbook_id,
        confidence_pct=confidence_pct,
        notes=notes,
    )
    RunbookInventoryService(docs_registry=registry).refresh(no_write=False)
    return {
        "status": "ok",
        "review_log": review.to_dict(),
        "evidence": evidence_entry.__dict__,
    }


def runbook_sync(
    *,
    no_write: bool = False,
    runbooks_dir: Path = Path("docs/runbooks"),
    governance_dir: Path = Path("reports/governance"),
    audit_dir: Path = Path("reports/audit"),
    templates_dir: Path = Path("docs/templates"),
    onboarding_path: Path = Path("docs/onboarding.md"),
    registry_path: Path = Path("reports/governance/docs_registry.json"),
    review_log_path: Path = Path("reports/governance/doc_review_log.jsonl"),
    inventory_path: Path = Path("reports/governance/runbook_inventory_status.json"),
    metrics_path: Path = Path("metrics/docops.jsonl"),
    event_log_path: Path = Path("logs/events/docops.jsonl"),
) -> Mapping[str, Any]:
    registry = DocsRegistry(
        runbooks_dir=runbooks_dir,
        governance_dir=governance_dir,
        audit_dir=audit_dir,
        templates_dir=templates_dir,
        onboarding_path=onboarding_path,
        registry_path=registry_path,
        review_log_path=review_log_path,
        event_log_path=event_log_path,
    )
    registry_payload = registry.sync(no_write=no_write)
    inventory = RunbookInventoryService(
        docs_registry=registry,
        inventory_path=inventory_path,
        metrics_path=metrics_path,
        event_log_path=event_log_path,
    ).refresh(no_write=no_write)
    return {
        "status": "ok",
        "registry_count": len(registry_payload.get("documents", [])),
        "runbook_count": len(inventory.runbooks),
        "summary": inventory.summary,
        "registry_path": str(registry_path),
        "inventory_path": str(inventory_path),
    }


def _append_validation_review(
    path: Path, *, runbook_id: str, evidence_path: Path, notes: str
) -> None:
    data = {}
    if path.exists():
        try:
            import yaml

            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    entries = list(data.get("entries") or [])
    entries.append(
        {
            "recorded_at": _utcnow_iso(),
            "runbook_id": runbook_id,
            "evidence_path": str(evidence_path),
            "notes": notes,
        }
    )
    data["entries"] = entries
    if "validation_playbook_id" not in data:
        data["validation_playbook_id"] = path.stem.replace("_runbook", "")
    path.write_text(_dump_yaml(data), encoding="utf-8")


def _dump_yaml(data: dict[str, object]) -> str:
    lines: list[str] = []
    if "validation_playbook_id" in data:
        lines.append(f"validation_playbook_id: {data['validation_playbook_id']}")
    lines.append("entries:")
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        lines.append(f"  - recorded_at: {entry.get('recorded_at')}")
        lines.append(f"    runbook_id: {entry.get('runbook_id')}")
        lines.append(f"    evidence_path: {entry.get('evidence_path')}")
        lines.append(f"    notes: {entry.get('notes')}")
    return "\n".join(lines) + "\n"


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["runbook_status", "runbook_review", "runbook_sync", "DocRegistryError", "DocValidationError"]
