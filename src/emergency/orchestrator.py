"""Emergency Orchestrator scaffold (Design §19.1)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:  # pragma: no cover - optional dependency
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# OpsWorklog no-op stub
# ---------------------------------------------------------------------------
#
# The legacy ``src.ops.worklog`` module was archived to
# ``archive/governance/src/ops/worklog.py`` as part of the personal-use
# simplification (see ``CLAUDE.md``). This file still accepts and records
# worklog entries on the public surface, but persistence is a no-op until a
# lean replacement lands in Phase 2 (if still needed).


@dataclass(slots=True)
class OpsWorklogEntry:
    """Minimal stub mirroring the archived ``src.ops.worklog.OpsWorklogEntry``."""

    schema_version: str
    ts: datetime
    task: str
    duration_min: int
    owner: str
    mode: str
    source: str
    related_artifacts: list[str]
    health_state: str
    board_mode: str
    notes: str | None = None


class OpsWorklogService:
    """No-op stub. ``record()`` drops the entry silently."""

    def __init__(self, *, ledger_path: Path = Path("ops_worklog.jsonl")) -> None:
        self._ledger_path = ledger_path

    def record(self, entry: OpsWorklogEntry) -> None:  # noqa: ARG002
        return None

DEFAULT_PLAYBOOK_CONFIG = Path("config/emergency.yaml")
DEFAULT_STATE_PATH = Path("data/emergency/state.json")
DEFAULT_EVENT_LOG = Path("logs/events/emergency_playbook.jsonl")
DEFAULT_AUDIT_LOG = Path("logs/audit/emergency.jsonl")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class EmergencyContext:
    health_state: str
    kill_switch: str
    board_mode: str
    metrics: dict[str, Any] = field(default_factory=dict)
    runbook_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "health_state": self.health_state,
            "kill_switch": self.kill_switch,
            "board_mode": self.board_mode,
            "metrics": dict(self.metrics),
            "runbook_refs": list(self.runbook_refs),
        }


@dataclass(slots=True)
class EmergencyPlaybook:
    playbook_id: str
    trigger: str
    runbook_refs: list[str]
    action_sequence: list[str]
    severity: str = "critical"
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "playbook_id": self.playbook_id,
            "trigger": self.trigger,
            "runbook_refs": list(self.runbook_refs),
            "action_sequence": list(self.action_sequence),
            "severity": self.severity,
            "description": self.description,
        }


@dataclass(slots=True)
class PlaybookState:
    playbook_id: str
    status: str
    triggered_at: str
    trigger: str
    runbook_refs: list[str]
    acked_by: str | None = None
    acked_at: str | None = None
    completed_by: str | None = None
    completed_at: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "playbook_id": self.playbook_id,
            "status": self.status,
            "triggered_at": self.triggered_at,
            "trigger": self.trigger,
            "runbook_refs": list(self.runbook_refs),
            "acked_by": self.acked_by,
            "acked_at": self.acked_at,
            "completed_by": self.completed_by,
            "completed_at": self.completed_at,
            "notes": self.notes,
        }


class PlaybookRegistry:
    def __init__(self, *, config_path: Path = DEFAULT_PLAYBOOK_CONFIG) -> None:
        self._config_path = config_path
        self._playbooks: list[EmergencyPlaybook] = []
        self.reload()

    def reload(self) -> None:
        if not self._config_path.exists():
            self._playbooks = []
            return
        payload = self._load_yaml(self._config_path)
        playbooks = []
        raw_playbooks = payload.get("playbooks")
        if raw_playbooks is None:
            raw_playbooks = payload.get("actions", [])
        for raw in raw_playbooks or []:
            playbooks.append(
                EmergencyPlaybook(
                    playbook_id=str(raw.get("id") or raw.get("playbook_id")),
                    trigger=str(raw.get("trigger") or raw.get("id") or ""),
                    runbook_refs=list(raw.get("runbook_refs") or []),
                    action_sequence=list(raw.get("action_sequence") or raw.get("steps") or []),
                    severity=str(raw.get("severity") or "critical"),
                    description=raw.get("description"),
                )
            )
        self._playbooks = playbooks

    def get_by_id(self, playbook_id: str) -> EmergencyPlaybook | None:
        for playbook in self._playbooks:
            if playbook.playbook_id == playbook_id:
                return playbook
        return None

    def find_by_trigger(self, trigger: str) -> EmergencyPlaybook | None:
        for playbook in self._playbooks:
            if playbook.trigger == trigger:
                return playbook
        return None

    def list(self) -> list[EmergencyPlaybook]:
        return list(self._playbooks)

    def _load_yaml(self, path: Path) -> Mapping[str, Any]:
        if yaml is None:
            from yaml import safe_load  # type: ignore[import-not-found]

            return safe_load(path.read_text(encoding="utf-8")) or {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


class EmergencyOrchestrator:
    def __init__(
        self,
        *,
        registry: PlaybookRegistry | None = None,
        state_path: Path = DEFAULT_STATE_PATH,
        event_log: Path = DEFAULT_EVENT_LOG,
        audit_log: Path = DEFAULT_AUDIT_LOG,
        worklog: OpsWorklogService | None = None,
    ) -> None:
        self._registry = registry or PlaybookRegistry()
        self._state_path = state_path
        self._event_log = event_log
        self._audit_log = audit_log
        self._worklog = worklog or OpsWorklogService()

    def trigger(
        self,
        *,
        trigger: str,
        context: EmergencyContext,
        playbook_id: str | None = None,
        actor: str = "system",
        simulate: bool = False,
    ) -> dict[str, Any]:
        playbook = self._select_playbook(trigger, playbook_id)
        if playbook is None:
            return {"status": "not_found", "trigger": trigger, "playbook_id": playbook_id}
        payload = {
            "event": "EmergencyPlaybookTriggered",
            "schema_version": "emergency.playbook.v1",
            "ts": _utcnow_iso(),
            "playbook": playbook.to_dict(),
            "context": context.to_dict(),
            "actor": actor,
            "simulated": simulate,
        }
        if simulate:
            return {"status": "simulated", "payload": payload}
        state = PlaybookState(
            playbook_id=playbook.playbook_id,
            status="pending",
            triggered_at=payload["ts"],
            trigger=trigger,
            runbook_refs=playbook.runbook_refs,
        )
        self._save_state(state)
        self._append_jsonl(self._event_log, payload)
        self._append_audit(
            {
                "event": "audit.emergency",
                "ts": payload["ts"],
                "action": "playbook_trigger",
                "playbook_id": playbook.playbook_id,
                "trigger": trigger,
                "actor": actor,
                "runbook_refs": playbook.runbook_refs,
            }
        )
        return {"status": "triggered", "playbook": playbook.to_dict(), "state": state.to_dict()}

    def ack(self, playbook_id: str, *, actor: str, notes: str | None = None) -> dict[str, Any]:
        state = self._load_state(playbook_id)
        if state is None:
            return {"status": "not_found", "playbook_id": playbook_id}
        if state.status != "pending":
            return {"status": "invalid_state", "state": state.to_dict()}
        state.status = "acknowledged"
        state.acked_by = actor
        state.acked_at = _utcnow_iso()
        state.notes = notes
        self._save_state(state)
        self._append_event("EmergencyPlaybookAcked", state, actor=actor, notes=notes)
        self._record_worklog(task="emergency_playbook", notes=f"ack {playbook_id}")
        return {"status": "ok", "state": state.to_dict()}

    def complete(
        self,
        playbook_id: str,
        *,
        actor: str,
        status: str = "completed",
        notes: str | None = None,
    ) -> dict[str, Any]:
        state = self._load_state(playbook_id)
        if state is None:
            return {"status": "not_found", "playbook_id": playbook_id}
        state.status = status
        state.completed_by = actor
        state.completed_at = _utcnow_iso()
        state.notes = notes
        self._save_state(state)
        self._append_event("EmergencyPlaybookCompleted", state, actor=actor, notes=notes)
        self._append_audit(
            {
                "event": "audit.emergency",
                "ts": state.completed_at,
                "action": "playbook_completed",
                "playbook_id": playbook_id,
                "actor": actor,
                "status": status,
                "runbook_refs": state.runbook_refs,
            }
        )
        return {"status": "ok", "state": state.to_dict()}

    def status(self) -> list[dict[str, Any]]:
        return [state.to_dict() for state in self._load_all_states()]

    def _select_playbook(self, trigger: str, playbook_id: str | None) -> EmergencyPlaybook | None:
        if playbook_id:
            return self._registry.get_by_id(playbook_id)
        return self._registry.find_by_trigger(trigger)

    def _load_all_states(self) -> list[PlaybookState]:
        if not self._state_path.exists():
            return []
        payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        states = []
        for raw in payload.get("playbooks", []):
            states.append(
                PlaybookState(
                    playbook_id=str(raw.get("playbook_id") or ""),
                    status=str(raw.get("status") or "pending"),
                    triggered_at=str(raw.get("triggered_at") or ""),
                    trigger=str(raw.get("trigger") or ""),
                    runbook_refs=list(raw.get("runbook_refs") or []),
                    acked_by=raw.get("acked_by"),
                    acked_at=raw.get("acked_at"),
                    completed_by=raw.get("completed_by"),
                    completed_at=raw.get("completed_at"),
                    notes=raw.get("notes"),
                )
            )
        return states

    def _load_state(self, playbook_id: str) -> PlaybookState | None:
        for state in self._load_all_states():
            if state.playbook_id == playbook_id:
                return state
        return None

    def _save_state(self, state: PlaybookState) -> None:
        states = [entry for entry in self._load_all_states() if entry.playbook_id != state.playbook_id]
        states.append(state)
        payload = {"playbooks": [entry.to_dict() for entry in states]}
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_event(self, event: str, state: PlaybookState, *, actor: str, notes: str | None) -> None:
        payload = {
            "event": event,
            "ts": _utcnow_iso(),
            "playbook_id": state.playbook_id,
            "status": state.status,
            "actor": actor,
            "notes": notes,
            "runbook_refs": state.runbook_refs,
        }
        self._append_jsonl(self._event_log, payload)

    def _append_jsonl(self, path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(payload), ensure_ascii=False))
            handle.write("\n")

    def _append_audit(self, payload: Mapping[str, Any]) -> None:
        self._audit_log.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(payload), ensure_ascii=False))
            handle.write("\n")

    def _record_worklog(self, *, task: str, notes: str | None = None) -> None:
        entry = OpsWorklogEntry(
            schema_version="ops_worklog.v1",
            ts=datetime.now(timezone.utc),
            task=task,
            duration_min=0,
            owner="emergency_orchestrator",
            mode="ops",
            source="emergency",
            related_artifacts=[],
            health_state="unknown",
            board_mode="unknown",
            notes=notes,
        )
        try:
            self._worklog.record(entry)
        except Exception:
            return


__all__ = [
    "EmergencyContext",
    "EmergencyPlaybook",
    "EmergencyOrchestrator",
    "PlaybookRegistry",
    "PlaybookState",
]
