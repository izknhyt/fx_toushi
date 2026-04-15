"""Strategy sunset orchestration."""

from __future__ import annotations

import hashlib
import json
import secrets
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.ops.evidence import OpsEvidenceStore

DEFAULT_SUNSET_DIR = Path("reports") / "governance" / "sunset"
DEFAULT_EVENT_LOG = Path("logs") / "events" / "strategy_sunset.jsonl"
DEFAULT_AUDIT_LOG = Path("logs") / "audit" / "strategy_sunset.jsonl"
DEFAULT_METRICS_PATH = Path("metrics") / "strategy_sunset.jsonl"
DEFAULT_VALIDATION_PLAYBOOK = Path("docs") / "validation_playbook" / "AC55_sunset.yaml"
DEFAULT_RUNBOOK_ID = "STRAT-SUNSET-01"
DEFAULT_EVIDENCE_LEDGER = Path("logs") / "audit" / "sunset_evidence.jsonl"
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")


class StrategySunsetError(RuntimeError):
    """Raised when sunset workflow fails."""


class SunsetIncompleteError(StrategySunsetError):
    """Raised when completion is attempted with open steps."""


@dataclass(slots=True)
class OpenPositionSnapshot:
    instrument: str
    direction: str
    size: float
    entry_price: float
    sl: float | None
    tp: float | None
    unrealized_r: float | None
    broker_ticket_id: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "instrument": self.instrument,
            "direction": self.direction,
            "size": self.size,
            "entry_price": self.entry_price,
            "sl": self.sl,
            "tp": self.tp,
            "unrealized_r": self.unrealized_r,
            "broker_ticket_id": self.broker_ticket_id,
        }


@dataclass(slots=True)
class ActionItem:
    step_id: str
    action: str
    owner: str
    runbook_ref: str
    status: str = "pending"
    evidence_path: str | None = None
    note: str | None = None
    completed_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "owner": self.owner,
            "runbook_ref": self.runbook_ref,
            "status": self.status,
            "evidence_path": self.evidence_path,
            "note": self.note,
            "completed_at": self.completed_at,
        }


@dataclass(slots=True)
class SunsetDirective:
    directive_id: str
    strategy_id: str
    issued_by: str
    issued_at: str
    reason: str
    effective_at: str
    gate_ref: str | None = None
    consent_reference_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "directive_id": self.directive_id,
            "strategy_id": self.strategy_id,
            "issued_by": self.issued_by,
            "issued_at": self.issued_at,
            "reason": self.reason,
            "effective_at": self.effective_at,
            "gate_ref": self.gate_ref,
            "consent_reference_id": self.consent_reference_id,
        }


@dataclass(slots=True)
class SunsetPlan:
    plan_id: str
    directive_id: str
    strategy_id: str
    open_positions: list[OpenPositionSnapshot]
    recommended_actions: list[ActionItem]
    capital_release_r: float | None
    expected_completion_at: str | None
    runbook_refs: list[str]
    validation_ids: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "strategy.sunset.plan.v1",
            "plan_id": self.plan_id,
            "directive_id": self.directive_id,
            "strategy_id": self.strategy_id,
            "open_positions": [pos.to_dict() for pos in self.open_positions],
            "recommended_actions": [step.to_dict() for step in self.recommended_actions],
            "capital_release_r": self.capital_release_r,
            "expected_completion_at": self.expected_completion_at,
            "runbook_refs": list(self.runbook_refs),
            "validation_ids": list(self.validation_ids),
        }


@dataclass(slots=True)
class SunsetExecutionLog:
    plan_id: str
    step_id: str
    executed_by: str
    executed_at: str
    action: str
    result: str
    evidence_hash: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "step_id": self.step_id,
            "executed_by": self.executed_by,
            "executed_at": self.executed_at,
            "action": self.action,
            "result": self.result,
            "evidence_hash": self.evidence_hash,
        }


@dataclass(slots=True)
class SunsetCompletionReceipt:
    plan_id: str
    strategy_id: str
    status: str
    completed_at: str
    reallocation_status: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "strategy_id": self.strategy_id,
            "status": self.status,
            "completed_at": self.completed_at,
            "reallocation_status": self.reallocation_status,
        }


class StrategySunsetService:
    def __init__(
        self,
        *,
        sunset_dir: Path = DEFAULT_SUNSET_DIR,
        event_log: Path = DEFAULT_EVENT_LOG,
        audit_log: Path = DEFAULT_AUDIT_LOG,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        validation_playbook_path: Path = DEFAULT_VALIDATION_PLAYBOOK,
        evidence_ledger: Path = DEFAULT_EVIDENCE_LEDGER,
        ops_worklog_path: Path = DEFAULT_OPS_WORKLOG,
        runbook_id: str = DEFAULT_RUNBOOK_ID,
    ) -> None:
        self._sunset_dir = sunset_dir
        self._event_log = event_log
        self._audit_log = audit_log
        self._metrics_path = metrics_path
        self._validation_playbook_path = validation_playbook_path
        self._runbook_id = runbook_id
        self._evidence_store = OpsEvidenceStore(
            ledger_path=evidence_ledger,
            playbook_dir=validation_playbook_path.parent,
            ops_worklog_path=ops_worklog_path,
        )

    def issue_directive(
        self,
        *,
        strategy_id: str,
        reason: str,
        issued_by: str,
        effective_at: str,
        gate_ref: str | None,
        consent_reference_id: str | None,
        dry_run: bool = False,
    ) -> SunsetDirective:
        directive = SunsetDirective(
            directive_id=_uuid7(),
            strategy_id=strategy_id,
            issued_by=issued_by,
            issued_at=_utcnow_iso(),
            reason=reason,
            effective_at=effective_at,
            gate_ref=gate_ref,
            consent_reference_id=consent_reference_id,
        )
        if dry_run:
            return directive
        path = self._directive_path(strategy_id, directive.directive_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(directive.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._append_event(
            {
                "event": "strategy.sunset_issued",
                "ts": _utcnow_iso(),
                "strategy_id": strategy_id,
                "directive_id": directive.directive_id,
                "reason": reason,
            }
        )
        self._append_audit(
            {
                "event": "audit.strategy_sunset_directive",
                "ts": _utcnow_iso(),
                "strategy_id": strategy_id,
                "directive_id": directive.directive_id,
                "runbook_ref": self._runbook_id,
                "consent_reference_id": consent_reference_id,
            }
        )
        return directive

    def build_plan(
        self,
        directive: SunsetDirective,
        *,
        fetch_positions: bool = True,
    ) -> SunsetPlan:
        positions = _load_positions(directive.strategy_id) if fetch_positions else []
        actions = _build_actions(positions)
        plan = SunsetPlan(
            plan_id=_uuid7(),
            directive_id=directive.directive_id,
            strategy_id=directive.strategy_id,
            open_positions=positions,
            recommended_actions=actions,
            capital_release_r=None,
            expected_completion_at=None,
            runbook_refs=[self._runbook_id],
            validation_ids=[self._validation_playbook_path.stem],
        )
        path = self._plan_path(directive.strategy_id, plan.plan_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._append_event(
            {
                "event": "strategy.sunset_plan_ready",
                "ts": _utcnow_iso(),
                "strategy_id": directive.strategy_id,
                "plan_id": plan.plan_id,
            }
        )
        self._append_audit(
            {
                "event": "audit.strategy_sunset_plan",
                "ts": _utcnow_iso(),
                "strategy_id": directive.strategy_id,
                "plan_id": plan.plan_id,
                "runbook_ref": self._runbook_id,
            }
        )
        self._append_metrics(plan, steps_completed=0)
        return plan

    def execute_step(
        self,
        plan_id: str,
        *,
        step_id: str,
        executed_by: str,
        evidence_path: Path | None,
        note: str | None,
    ) -> SunsetExecutionLog:
        plan = self._load_plan(plan_id)
        step = _find_step(plan.recommended_actions, step_id)
        if step.status == "completed":
            return SunsetExecutionLog(
                plan_id=plan.plan_id,
                step_id=step.step_id,
                executed_by=executed_by,
                executed_at=step.completed_at or _utcnow_iso(),
                action=step.action,
                result="already_completed",
                evidence_hash=None,
            )
        now = _utcnow_iso()
        if not evidence_path:
            raise StrategySunsetError("evidence_required")
        if evidence_path and not evidence_path.exists():
            raise StrategySunsetError(f"evidence missing: {evidence_path}")
        evidence_hash = _hash_path(evidence_path) if evidence_path else None
        step.status = "completed"
        step.completed_at = now
        step.note = note
        if evidence_path:
            step.evidence_path = str(evidence_path)
            self._evidence_store.register(
                category="strategy_sunset",
                artifact=evidence_path,
                runbook_refs=[self._runbook_id],
                notes=note or "sunset step evidence",
            )
        self._persist_plan(plan)
        log = SunsetExecutionLog(
            plan_id=plan.plan_id,
            step_id=step.step_id,
            executed_by=executed_by,
            executed_at=now,
            action=step.action,
            result="completed",
            evidence_hash=evidence_hash,
        )
        self._append_event(
            {
                "event": "strategy.sunset_step_completed",
                "ts": now,
                "strategy_id": plan.strategy_id,
                "plan_id": plan.plan_id,
                "step_id": step_id,
            }
        )
        self._append_audit(
            {
                "event": "audit.strategy_sunset_step",
                "ts": now,
                "strategy_id": plan.strategy_id,
                "plan_id": plan.plan_id,
                "step_id": step_id,
                "evidence_hash": evidence_hash,
            }
        )
        self._append_metrics(plan, steps_completed=_count_completed(plan.recommended_actions))
        return log

    def complete(self, plan_id: str, *, reallocation_status: str | None = None) -> SunsetCompletionReceipt:
        plan = self._load_plan(plan_id)
        if not _all_steps_completed(plan.recommended_actions):
            raise SunsetIncompleteError("sunset steps incomplete")
        now = _utcnow_iso()
        receipt = SunsetCompletionReceipt(
            plan_id=plan.plan_id,
            strategy_id=plan.strategy_id,
            status="completed",
            completed_at=now,
            reallocation_status=reallocation_status,
        )
        self._append_event(
            {
                "event": "strategy.sunset_completed",
                "ts": now,
                "strategy_id": plan.strategy_id,
                "plan_id": plan.plan_id,
            }
        )
        self._append_audit(
            {
                "event": "audit.strategy_sunset_complete",
                "ts": now,
                "strategy_id": plan.strategy_id,
                "plan_id": plan.plan_id,
                "reallocation_status": reallocation_status,
            }
        )
        self._append_validation_entry(plan, receipt)
        self._append_metrics(plan, steps_completed=_count_completed(plan.recommended_actions))
        return receipt

    def load_plan(self, plan_id: str) -> SunsetPlan:
        return self._load_plan(plan_id)

    def _append_validation_entry(self, plan: SunsetPlan, receipt: SunsetCompletionReceipt) -> None:
        path = self._validation_playbook_path
        payload = {}
        if path.exists():
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            payload = {}
        if "validation_playbook_id" not in payload:
            payload["validation_playbook_id"] = path.stem
        if "category" not in payload:
            payload["category"] = "strategy_sunset"
        entries = list(payload.get("entries") or [])
        entries.append(
            {
                "plan_id": plan.plan_id,
                "strategy_id": plan.strategy_id,
                "status": receipt.status,
                "completed_at": receipt.completed_at,
            }
        )
        payload["entries"] = entries
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_dump_yaml(payload), encoding="utf-8")

    def _append_metrics(self, plan: SunsetPlan, *, steps_completed: int) -> None:
        payload = {
            "metric": "strategy_sunset",
            "ts": _utcnow_iso(),
            "strategy_id": plan.strategy_id,
            "plan_id": plan.plan_id,
            "open_positions_count": len(plan.open_positions),
            "steps_total": len(plan.recommended_actions),
            "steps_completed": steps_completed,
        }
        _append_event(self._metrics_path, payload)

    def _append_event(self, payload: Mapping[str, object]) -> None:
        _append_event(self._event_log, payload)

    def _append_audit(self, payload: Mapping[str, object]) -> None:
        _append_event(self._audit_log, payload)

    def _directive_path(self, strategy_id: str, directive_id: str) -> Path:
        return self._sunset_dir / strategy_id / f"directive_{directive_id}.json"

    def _plan_path(self, strategy_id: str, plan_id: str) -> Path:
        return self._sunset_dir / strategy_id / f"plan_{plan_id}.json"

    def _load_plan(self, plan_id: str) -> SunsetPlan:
        for path in self._sunset_dir.glob("*/plan_*.json"):
            if path.stem == f"plan_{plan_id}":
                payload = json.loads(path.read_text(encoding="utf-8"))
                return _parse_plan(payload)
        raise StrategySunsetError(f"plan not found: {plan_id}")

    def _persist_plan(self, plan: SunsetPlan) -> None:
        path = self._plan_path(plan.strategy_id, plan.plan_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_plan(payload: Mapping[str, Any]) -> SunsetPlan:
    positions = []
    for raw in payload.get("open_positions") or []:
        positions.append(
            OpenPositionSnapshot(
                instrument=str(raw.get("instrument") or ""),
                direction=str(raw.get("direction") or ""),
                size=float(raw.get("size") or 0),
                entry_price=float(raw.get("entry_price") or 0),
                sl=raw.get("sl"),
                tp=raw.get("tp"),
                unrealized_r=raw.get("unrealized_r"),
                broker_ticket_id=raw.get("broker_ticket_id"),
            )
        )
    actions = []
    for raw in payload.get("recommended_actions") or []:
        actions.append(
            ActionItem(
                step_id=str(raw.get("step_id") or ""),
                action=str(raw.get("action") or ""),
                owner=str(raw.get("owner") or ""),
                runbook_ref=str(raw.get("runbook_ref") or DEFAULT_RUNBOOK_ID),
                status=str(raw.get("status") or "pending"),
                evidence_path=raw.get("evidence_path"),
                note=raw.get("note"),
                completed_at=raw.get("completed_at"),
            )
        )
    return SunsetPlan(
        plan_id=str(payload.get("plan_id") or ""),
        directive_id=str(payload.get("directive_id") or ""),
        strategy_id=str(payload.get("strategy_id") or ""),
        open_positions=positions,
        recommended_actions=actions,
        capital_release_r=payload.get("capital_release_r"),
        expected_completion_at=payload.get("expected_completion_at"),
        runbook_refs=list(payload.get("runbook_refs") or []),
        validation_ids=list(payload.get("validation_ids") or []),
    )


def _load_positions(strategy_id: str) -> list[OpenPositionSnapshot]:
    path = Path("reports") / "performance" / "portfolio" / "open_positions.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    positions = []
    for raw in payload.get("positions") or []:
        positions.append(
            OpenPositionSnapshot(
                instrument=str(raw.get("instrument") or ""),
                direction=str(raw.get("direction") or ""),
                size=float(raw.get("size") or 0),
                entry_price=float(raw.get("entry_price") or 0),
                sl=raw.get("sl"),
                tp=raw.get("tp"),
                unrealized_r=raw.get("unrealized_r"),
                broker_ticket_id=raw.get("broker_ticket_id"),
            )
        )
    return positions


def _build_actions(positions: list[OpenPositionSnapshot]) -> list[ActionItem]:
    actions: list[ActionItem] = []
    if not positions:
        actions.append(
            ActionItem(
                step_id="manual_review",
                action="Review open positions and confirm closure",
                owner="ops",
                runbook_ref=DEFAULT_RUNBOOK_ID,
            )
        )
        return actions
    for idx, position in enumerate(positions, start=1):
        actions.append(
            ActionItem(
                step_id=f"close_{idx}",
                action=f"Close {position.instrument} ({position.direction})",
                owner="ops",
                runbook_ref=DEFAULT_RUNBOOK_ID,
            )
        )
    return actions


def _find_step(steps: list[ActionItem], step_id: str) -> ActionItem:
    for step in steps:
        if step.step_id == step_id:
            return step
    raise StrategySunsetError(f"step not found: {step_id}")


def _count_completed(steps: list[ActionItem]) -> int:
    return sum(1 for step in steps if step.status == "completed")


def _all_steps_completed(steps: list[ActionItem]) -> bool:
    return all(step.status == "completed" for step in steps)


def _append_event(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(payload), ensure_ascii=False) + "\n")


def _dump_yaml(payload: Mapping[str, object]) -> str:
    dumper = getattr(yaml, "safe_dump", None)
    if dumper:
        return dumper(dict(payload), sort_keys=False)
    return "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2)


def _hash_path(path: Path | None) -> str | None:
    if not path:
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _uuid7() -> str:
    ts_ms = time.time_ns() // 1_000_000
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (ts_ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0b10 << 62
    value |= rand_b
    return str(uuid.UUID(int=value))


__all__ = [
    "StrategySunsetService",
    "SunsetDirective",
    "SunsetPlan",
    "SunsetExecutionLog",
    "SunsetCompletionReceipt",
    "StrategySunsetError",
    "SunsetIncompleteError",
]
