"""Scaffolding for AutomationEffectTracker as described in design §52.2."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

AUTOMATION_EFFECT_JSONL_PATH = Path("automation_effect.jsonl")
"""Default ledger containing automation effect measurements."""

OPS_AUTOMATION_METRICS_PATH = Path("metrics/ops_automation.jsonl")
"""Derived metrics log for automation gains."""

OPS_AUTOMATION_AUDIT_PATH = Path("logs/audit/ops_automation.jsonl")
"""Audit trail for automation effect entries."""

AUTOMATION_EFFECT_ACHIEVED_EVENT = "automation.effect_achieved"
"""Event emitted when an automation gain crosses the configured threshold."""

AUTOMATION_GAIN_THRESHOLD_MIN = 10
"""Minimum gain in minutes that triggers an achieved event."""

class AutomationEffectError(Exception):
    """Base exception for automation effect tracking."""


class AutomationEffectValidationError(AutomationEffectError):
    """Raised when an automation delta fails domain validation."""


@dataclass(slots=True)
class AutomationEffectEntry:
    """Representation of a persisted automation effect measurement."""

    schema_version: str
    ts: datetime
    task: str
    before_min: int
    after_min: int
    gain_min: int
    effective_date: date
    runbook_ref: str
    status: str
    evidence: list[str]


@dataclass(slots=True)
class AutomationEffectDelta:
    """Change request applied through :meth:`AutomationEffectTracker.apply`."""

    task: str
    before_min: int | None
    after_min: int | None
    effective_date: date | None = None
    runbook_ref: str | None = None
    evidence: list[str] | None = None


class AutomationEffectTracker:
    """Service responsible for updating ``automation_effect.jsonl`` entries."""

    def __init__(
        self,
        *,
        ledger_path: Path = AUTOMATION_EFFECT_JSONL_PATH,
        metrics_path: Path = OPS_AUTOMATION_METRICS_PATH,
        audit_path: Path = OPS_AUTOMATION_AUDIT_PATH,
        gain_threshold_min: int = AUTOMATION_GAIN_THRESHOLD_MIN,
    ) -> None:
        """Create a tracker bound to the provided JSONL ledger path."""

        self._ledger_path = ledger_path
        self._metrics_path = metrics_path
        self._audit_path = audit_path
        self._gain_threshold_min = gain_threshold_min

    def apply(self, delta: AutomationEffectDelta) -> AutomationEffectEntry:
        """Apply *delta* and emit ``automation.effect_achieved`` when the gain exceeds policy."""

        if delta.task is None:
            raise AutomationEffectValidationError("task is required")
        entry = AutomationEffectEntry(
            schema_version="automation.effect.v1",
            ts=datetime.now(timezone.utc),
            task=delta.task,
            before_min=delta.before_min or 0,
            after_min=delta.after_min or 0,
            gain_min=(delta.before_min or 0) - (delta.after_min or 0),
            effective_date=delta.effective_date or date.today(),
            runbook_ref=delta.runbook_ref or "",
            status="ok",
            evidence=list(delta.evidence or []),
        )
        payload = {
            "schema_version": entry.schema_version,
            "ts": entry.ts.isoformat().replace("+00:00", "Z"),
            "task": entry.task,
            "before_min": entry.before_min,
            "after_min": entry.after_min,
            "gain_min": entry.gain_min,
            "effective_date": entry.effective_date.isoformat(),
            "runbook_ref": entry.runbook_ref,
            "status": entry.status,
            "evidence": entry.evidence,
        }
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")
        except OSError as exc:
            raise AutomationEffectError(str(exc)) from exc
        self._append_audit(payload)
        if entry.gain_min >= self._gain_threshold_min:
            self._append_metrics(entry)
        return entry

    def iter_effects(self, task: str | None = None) -> Iterable[AutomationEffectEntry]:
        """Iterate over persisted automation effect entries, optionally filtered by *task*."""

        if not self._ledger_path.exists():
            return ()
        entries: list[AutomationEffectEntry] = []
        for line in self._ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if task and data.get("task") != task:
                continue
            try:
                ts = datetime.fromisoformat(str(data.get("ts")).replace("Z", "+00:00"))
                effective_date = date.fromisoformat(str(data.get("effective_date")))
            except Exception:
                continue
            entries.append(
                AutomationEffectEntry(
                    schema_version=str(data.get("schema_version", "")),
                    ts=ts,
                    task=str(data.get("task", "")),
                    before_min=int(data.get("before_min", 0)),
                    after_min=int(data.get("after_min", 0)),
                    gain_min=int(data.get("gain_min", 0)),
                    effective_date=effective_date,
                    runbook_ref=str(data.get("runbook_ref", "")),
                    status=str(data.get("status", "")),
                    evidence=list(data.get("evidence", [])),
                )
            )
        return entries

    def _append_metrics(self, entry: AutomationEffectEntry) -> None:
        payload = {
            "event": AUTOMATION_EFFECT_ACHIEVED_EVENT,
            "ts": entry.ts.isoformat().replace("+00:00", "Z"),
            "task": entry.task,
            "gain_min": entry.gain_min,
            "status": entry.status,
        }
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _append_audit(self, payload: dict[str, object]) -> None:
        audit_payload = {
            "event": "audit.ops_automation",
            "ts": payload.get("ts"),
            "task": payload.get("task"),
            "entry_hash": _hash_payload(payload),
            "evidence": payload.get("evidence"),
        }
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_payload, ensure_ascii=False))
            handle.write("\n")


def _hash_payload(payload: dict[str, object]) -> str:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
