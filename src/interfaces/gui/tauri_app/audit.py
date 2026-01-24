"""Audit writer for GUI board actions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


@dataclass(slots=True)
class GuiAuditWriter:
    path: Path = Path("logs/audit/gui_board.jsonl")
    schema_version: str = "gui.audit.v1"

    def record(
        self,
        *,
        action: str,
        ticket_id: str,
        user: str,
        status: str,
        source: str,
        category: str,
        delta: Mapping[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        audit_delta = _normalize_delta(delta, decision=status)
        entry = {
            "ts": _utcnow_iso(),
            "schema_version": self.schema_version,
            "record_type": "gui.audit",
            "action_category": category,
            "action": action,
            "ticket_id": ticket_id,
            "user": user,
            "status": status,
            "source": source,
            "delta": audit_delta,
            "error": error,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")
        return entry


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_delta(delta: Mapping[str, Any] | None, *, decision: str) -> dict[str, Any]:
    base = {"before": None, "after": None, "diff": {}, "decision": decision}
    if not delta:
        return dict(base)
    merged = dict(base)
    merged.update(delta)
    if "decision" not in merged or merged["decision"] in (None, ""):
        merged["decision"] = decision
    return merged


__all__ = ["GuiAuditWriter"]
