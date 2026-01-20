"""Runbook inventory generation for DocOps."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.docops.registry import DOCOPS_EVENT_LOG, DocsRegistry
from src.persistence.events import EventWriter

DEFAULT_INVENTORY_PATH = Path("reports/governance/runbook_inventory_status.json")
DEFAULT_METRICS_PATH = Path("metrics/docops.jsonl")


@dataclass(slots=True)
class RunbookInventory:
    runbooks: dict[str, dict[str, object]]
    summary: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": _utcnow_iso(),
            "runbooks": self.runbooks,
            "summary": self.summary,
        }


class RunbookInventoryService:
    def __init__(
        self,
        *,
        docs_registry: DocsRegistry | None = None,
        inventory_path: Path = DEFAULT_INVENTORY_PATH,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        event_log_path: Path = DOCOPS_EVENT_LOG,
    ) -> None:
        self._registry = docs_registry or DocsRegistry()
        self._inventory_path = inventory_path
        self._metrics_path = metrics_path
        self._event_log_path = event_log_path

    def refresh(self, *, no_write: bool = False) -> RunbookInventory:
        records = self._registry.scan()
        runbooks: dict[str, dict[str, object]] = {}
        counts = {"ready": 0, "grace": 0, "overdue": 0}
        for record in records:
            if record.category != "runbook":
                continue
            review_due_in_days = _days_until(record.next_review_due)
            status = record.status
            if review_due_in_days is not None:
                if review_due_in_days < 0:
                    status = "overdue"
                elif review_due_in_days <= 7:
                    status = "grace"
                else:
                    status = "ready"
            counts[status] = counts.get(status, 0) + 1
            runbooks[record.document_id] = {
                "title": record.title,
                "path": record.path,
                "category": _resolve_runbook_category(record.document_id),
                "doc_owner": record.owners[0] if record.owners else "unassigned",
                "owners": list(record.owners),
                "review_cycle_days": record.review_cycle_days,
                "next_review_due": record.next_review_due,
                "review_due_in_days": review_due_in_days,
                "status": status,
                "validation_playbook_ids": list(record.validation_playbook_ids),
                "evidence_path": record.last_review_log.get("evidence_path")
                if record.last_review_log
                else None,
            }
            if not no_write and review_due_in_days is not None:
                if 0 <= review_due_in_days <= 7:
                    self._emit_event(
                        "doc.review_due",
                        {
                            "document_id": record.document_id,
                            "days_to_due": review_due_in_days,
                        },
                    )
                elif review_due_in_days < 0:
                    self._emit_event(
                        "doc.review_overdue",
                        {
                            "document_id": record.document_id,
                            "days_overdue": abs(review_due_in_days),
                        },
                    )
        inventory = RunbookInventory(runbooks=runbooks, summary=counts)
        if not no_write:
            self._inventory_path.parent.mkdir(parents=True, exist_ok=True)
            self._inventory_path.write_text(
                json.dumps(inventory.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._append_metrics(counts)
        return inventory

    def _append_metrics(self, counts: dict[str, int]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": _utcnow_iso(),
            "metric": "runbook_status",
            "status_counts": counts,
        }
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _emit_event(self, event: str, payload: dict[str, object]) -> None:
        EventWriter(self._event_log_path).append(
            {
                "event": event,
                "ts": _utcnow_iso(),
                **payload,
            }
        )


def _days_until(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        target = datetime.fromisoformat(date_str).date()
    except ValueError:
        return None
    today = datetime.now(timezone.utc).date()
    return (target - today).days


def _resolve_runbook_category(runbook_id: str) -> str:
    prefix = runbook_id.split("-", 1)[0].upper()
    if prefix in {"RUN", "OPS"}:
        return "ops"
    if prefix in {"GOV", "COMPLIANCE"}:
        return "governance"
    if prefix in {"RISK"}:
        return "risk"
    if prefix in {"DATA"}:
        return "data"
    return "general"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["RunbookInventoryService", "RunbookInventory"]
