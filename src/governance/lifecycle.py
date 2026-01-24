"""Strategy lifecycle orchestration and gate evaluation."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

STATE_DIR = Path("reports/governance/lifecycle")
HISTORY_LOG = Path("data/governance/lifecycle_state.jsonl")
AUDIT_LOG = Path("logs/audit/lifecycle_gate.jsonl")
METRICS_PATH = Path("metrics/strategy_lifecycle.jsonl")
ROLES_PATH = Path("config/roles.yaml")


@dataclass(slots=True)
class LifecycleState:
    strategy_id: str
    current_stage: str
    gate_status: str
    blocked_reasons: list[str] = field(default_factory=list)
    last_gate_check: str | None = None
    board_decision_ref: str | None = None
    score_snapshot: dict[str, object] | None = None
    ops_readiness_score: float | None = None
    model_risk_status: str | None = None
    license_status: str | None = None
    capital_guard_status: str | None = None
    validation_playbook_ids: list[str] = field(default_factory=list)
    schema_version: str = "lifecycle_state.v1"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "strategy_id": self.strategy_id,
            "current_stage": self.current_stage,
            "gate_status": self.gate_status,
            "blocked_reasons": list(self.blocked_reasons),
            "last_gate_check": self.last_gate_check,
            "board_decision_ref": self.board_decision_ref,
            "score_snapshot": self.score_snapshot,
            "ops_readiness_score": self.ops_readiness_score,
            "model_risk_status": self.model_risk_status,
            "license_status": self.license_status,
            "capital_guard_status": self.capital_guard_status,
            "validation_playbook_ids": list(self.validation_playbook_ids),
        }


@dataclass(slots=True)
class GateDefinition:
    gate_id: str
    description: str
    required_signals: list[str]
    thresholds: dict[str, dict[str, float]] = field(default_factory=dict)
    runbook_refs: list[str] = field(default_factory=list)
    validation_playbook_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "gate_id": self.gate_id,
            "description": self.description,
            "required_signals": list(self.required_signals),
            "thresholds": self.thresholds,
            "runbook_refs": list(self.runbook_refs),
            "validation_playbook_refs": list(self.validation_playbook_refs),
        }


@dataclass(slots=True)
class GateResult:
    gate_id: str
    status: str
    reasons: list[str]
    evidence_refs: list[str]
    next_actions: list[str]
    evaluated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "gate_id": self.gate_id,
            "status": self.status,
            "reasons": list(self.reasons),
            "evidence_refs": list(self.evidence_refs),
            "next_actions": list(self.next_actions),
            "evaluated_at": self.evaluated_at,
        }


class StrategyLifecycleOrchestrator:
    def __init__(
        self,
        *,
        state_dir: Path = STATE_DIR,
        history_log: Path = HISTORY_LOG,
        audit_log: Path = AUDIT_LOG,
        metrics_path: Path = METRICS_PATH,
        roles_path: Path = ROLES_PATH,
    ) -> None:
        self._state_dir = state_dir
        self._history_log = history_log
        self._audit_log = audit_log
        self._metrics_path = metrics_path
        self._roles_path = roles_path

    def list_gates(self) -> list[GateDefinition]:
        return _default_gates()

    def load_state(self, strategy_id: str) -> LifecycleState:
        path = self._state_dir / f"{strategy_id}.json"
        if not path.exists():
            return LifecycleState(strategy_id=strategy_id, current_stage="draft", gate_status="pending")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return LifecycleState(
            strategy_id=str(payload.get("strategy_id") or strategy_id),
            current_stage=str(payload.get("current_stage") or "draft"),
            gate_status=str(payload.get("gate_status") or "pending"),
            blocked_reasons=list(payload.get("blocked_reasons") or []),
            last_gate_check=payload.get("last_gate_check"),
            board_decision_ref=payload.get("board_decision_ref"),
            score_snapshot=payload.get("score_snapshot"),
            ops_readiness_score=_optional_float(payload.get("ops_readiness_score")),
            model_risk_status=payload.get("model_risk_status"),
            license_status=payload.get("license_status"),
            capital_guard_status=payload.get("capital_guard_status"),
            validation_playbook_ids=list(payload.get("validation_playbook_ids") or []),
        )

    def list_states(self) -> list[LifecycleState]:
        if not self._state_dir.exists():
            return []
        return [self.load_state(path.stem) for path in self._state_dir.glob("*.json")]

    def evaluate_gate(
        self,
        *,
        strategy_id: str,
        gate_id: str,
        signals: Mapping[str, object],
        actor: str,
        force: bool = False,
    ) -> GateResult:
        gate = next((g for g in self.list_gates() if g.gate_id == gate_id), None)
        if gate is None:
            raise ValueError(f"unknown gate: {gate_id}")
        if force and not _actor_has_role(actor, "lifecycle_override", self._roles_path):
            raise PermissionError("actor lacks lifecycle_override role")
        reasons: list[str] = []
        if not force:
            for signal in gate.required_signals:
                if not _signal_truthy(signals.get(signal)):
                    reasons.append(f"missing:{signal}")
            for key, rule in gate.thresholds.items():
                value = _optional_float(signals.get(key))
                if value is None:
                    reasons.append(f"missing:{key}")
                    continue
                min_value = rule.get("min")
                max_value = rule.get("max")
                if min_value is not None and value < min_value:
                    reasons.append(f"{key}<min")
                if max_value is not None and value > max_value:
                    reasons.append(f"{key}>max")
        status = "pass" if force or not reasons else "fail"
        result = GateResult(
            gate_id=gate_id,
            status=status,
            reasons=reasons if not force else ["forced_by_actor"],
            evidence_refs=list(gate.validation_playbook_refs),
            next_actions=["review_runbook"] if reasons else [],
            evaluated_at=_utcnow_iso(),
        )
        state = self.load_state(strategy_id)
        state.gate_status = status
        state.last_gate_check = result.evaluated_at
        if status == "fail":
            state.blocked_reasons = reasons
        else:
            state.blocked_reasons = []
        self._persist_state(state)
        self._append_history(state)
        self._append_audit(
            {
                "event": "audit.lifecycle_gate",
                "strategy_id": strategy_id,
                "gate_id": gate_id,
                "decision": status,
                "actor": actor,
                "reasons": reasons,
            }
        )
        self._append_metrics(
            {
                "strategy_id": strategy_id,
                "gate_id": gate_id,
                "gate_status": status,
                "blocked_reasons": reasons,
            }
        )
        return result

    def export_history(self, strategy_id: str) -> Path:
        entries = _read_history(self._history_log, strategy_id)
        output_dir = self._state_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"history_{strategy_id}.md"
        lines = [
            f"# Lifecycle History ({strategy_id})",
            "",
            "## Events",
        ]
        if not entries:
            lines.append("- none")
        for entry in entries:
            lines.append(f"- {entry.get('ts')}: {entry.get('gate_status')}")
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output_path

    def simulate(self, *, strategy_id: str, scenario: str) -> GateResult:
        scenarios = {
            "paper_promotion": ("gate.paper_promotion", {"alpha_score": 80, "ops_readiness_score": 85}),
            "live_promotion": ("gate.live_promotion", {"alpha_score": 85, "ops_readiness_score": 90}),
            "suspension": ("gate.live_continuation", {"alpha_score": 40, "ops_readiness_score": 60}),
        }
        gate_id, signals = scenarios.get(scenario, ("gate.paper_promotion", {}))
        return self.evaluate_gate(
            strategy_id=strategy_id,
            gate_id=gate_id,
            signals=signals,
            actor="simulation",
            force=False,
        )

    def _persist_state(self, state: LifecycleState) -> None:
        self._state_dir.mkdir(parents=True, exist_ok=True)
        path = self._state_dir / f"{state.strategy_id}.json"
        path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_history(self, state: LifecycleState) -> None:
        self._history_log.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ts": _utcnow_iso(), **state.to_dict()}
        with self._history_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _append_audit(self, payload: Mapping[str, object]) -> None:
        self._audit_log.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _utcnow_iso(), **payload}
        with self._audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")

    def _append_metrics(self, payload: Mapping[str, object]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _utcnow_iso(), **payload}
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")


def _default_gates() -> list[GateDefinition]:
    return [
        GateDefinition(
            gate_id="gate.paper_promotion",
            description="Promote strategy from screening to paper",
            required_signals=["idea.stage.screening", "strategy_board.decision.approve"],
            thresholds={"alpha_score": {"min": 75.0}, "ops_readiness_score": {"min": 80.0}},
            runbook_refs=["GOV-LIFECYCLE-01"],
            validation_playbook_refs=["strategy_lifecycle"],
        ),
        GateDefinition(
            gate_id="gate.live_promotion",
            description="Promote strategy from ready to live",
            required_signals=["strategy_board.decision.approve", "model_risk.green"],
            thresholds={"alpha_score": {"min": 80.0}, "ops_readiness_score": {"min": 85.0}},
            runbook_refs=["GOV-LIFECYCLE-01"],
            validation_playbook_refs=["strategy_lifecycle"],
        ),
        GateDefinition(
            gate_id="gate.live_continuation",
            description="Continue live trading eligibility",
            required_signals=["scoreboard.ok", "license.ok"],
            thresholds={"alpha_score": {"min": 60.0}, "ops_readiness_score": {"min": 75.0}},
            runbook_refs=["GOV-LIFECYCLE-01"],
            validation_playbook_refs=["strategy_lifecycle"],
        ),
    ]


def _signal_truthy(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        return value.strip().lower() not in {"", "false", "no", "0"}
    return True


def _actor_has_role(actor: str, role: str, roles_path: Path) -> bool:
    if not roles_path.exists():
        return False
    payload = yaml.safe_load(roles_path.read_text(encoding="utf-8")) or {}
    roles = payload.get("roles") if isinstance(payload, dict) else {}
    role_entry = roles.get(role) if isinstance(roles, dict) else None
    members = role_entry.get("members") if isinstance(role_entry, dict) else []
    for member in members or []:
        principal_id = member.get("principal_id") if isinstance(member, dict) else None
        if principal_id == actor:
            return True
    return False


def _read_history(path: Path, strategy_id: str) -> list[dict[str, object]]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("strategy_id") == strategy_id:
            entries.append(payload)
    return entries


def _optional_float(value: object | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["StrategyLifecycleOrchestrator", "LifecycleState", "GateDefinition", "GateResult"]
