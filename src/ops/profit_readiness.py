"""Helpers for tracking the profit readiness lever statuses."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_PROFIT_READINESS_PATH = Path("metrics/profit_readiness.jsonl")
ALLOWED_STATUSES = {"ok", "warning", "alert"}


class ProfitReadinessError(RuntimeError):
    """Raised when readiness records cannot be read or written."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: list[dict[str, Any]] = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


@dataclass(frozen=True)
class ProfitReadinessEntry:
    lever: str
    status: str
    evidence: list[str]
    notes: str | None
    actor: str | None
    timestamp: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "lever": self.lever,
            "status": self.status,
            "evidence": list(self.evidence),
            "notes": self.notes,
            "actor": self.actor,
            "timestamp": self.timestamp,
        }


def record_readiness(
    *,
    lever: str,
    status: str,
    evidence: Iterable[str] | None = None,
    notes: str | None = None,
    actor: str | None = None,
    path: Path = DEFAULT_PROFIT_READINESS_PATH,
) -> ProfitReadinessEntry:
    """Append a readiness event to metrics/profit_readiness.jsonl."""

    if status not in ALLOWED_STATUSES:
        raise ProfitReadinessError(f"Unsupported status '{status}'. Allowed: {sorted(ALLOWED_STATUSES)}")
    payload = ProfitReadinessEntry(
        lever=lever,
        status=status,
        evidence=list(evidence or []),
        notes=notes,
        actor=actor,
        timestamp=_utcnow(),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload.to_mapping(), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return payload


def load_recent_readiness(
    *,
    path: Path = DEFAULT_PROFIT_READINESS_PATH,
    lever_filter: Iterable[str] | None = None,
    limit: int = 10,
) -> list[ProfitReadinessEntry]:
    """Return the most recent readiness entries, optionally filtered by lever."""

    entries = _read_jsonl(path)
    if lever_filter:
        allowed = {lever.lower() for lever in lever_filter}
        entries = [item for item in entries if item.get("lever", "").lower() in allowed]
    tail = entries[-limit:]
    return [
        ProfitReadinessEntry(
            lever=str(item.get("lever", "")),
            status=str(item.get("status", "ok")),
            evidence=list(item.get("evidence", [])),
            notes=item.get("notes"),
            actor=item.get("actor"),
            timestamp=str(item.get("timestamp", "")),
        )
        for item in tail
    ]


def latest_by_lever(
    *,
    path: Path = DEFAULT_PROFIT_READINESS_PATH,
    levers: Iterable[str] | None = None,
) -> dict[str, ProfitReadinessEntry]:
    """Return the most recent entry for each lever."""

    entries = _read_jsonl(path)
    levers_normalised = {lever.lower(): lever for lever in levers or []}
    latest: dict[str, ProfitReadinessEntry] = {}
    for item in entries:
        lever = str(item.get("lever", ""))
        if not lever:
            continue
        lower = lever.lower()
        if levers and lower not in levers_normalised:
            continue
        latest[lever] = ProfitReadinessEntry(
            lever=lever,
            status=str(item.get("status", "ok")),
            evidence=list(item.get("evidence", [])),
            notes=item.get("notes"),
            actor=item.get("actor"),
            timestamp=str(item.get("timestamp", "")),
        )
    return latest
