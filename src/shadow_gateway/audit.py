"""Audit sink for Shadow Gateway events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


@dataclass(slots=True)
class AuditSink:
    path: Path = Path("logs/audit/shadow_gateway.jsonl")

    def append(self, event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        entry = {"ts": _utcnow_iso(), "event_type": event_type, "payload": dict(payload)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")
        return entry


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["AuditSink"]
