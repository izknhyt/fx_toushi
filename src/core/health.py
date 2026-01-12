"""Lightweight health state management primitives used by the CLI."""

from __future__ import annotations

import copy
from collections.abc import Iterable
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from src.core.gate import GateState

__all__ = [
    "GuardrailSnapshot",
    "HealthAction",
    "HealthMonitor",
    "HealthReason",
    "HealthState",
    "KillSwitchSuggestion",
]


_SEVERITY_ORDER = ("ok", "warn", "degraded", "soft_stop", "hard_stop")
DEFAULT_HEALTH_EVENT_LOG = Path("logs/events/health.changed.jsonl")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class HealthReason:
    """Represents a concrete reason for being in a degraded state."""

    code: str
    level: str
    detail: str | None = None
    recommended_action: str | None = None
    raised_at: datetime = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "level": self.level,
            "detail": self.detail,
            "recommended_action": self.recommended_action,
            "raised_at": self.raised_at.isoformat(),
        }


@dataclass(slots=True)
class KillSwitchSuggestion:
    """Container for the Kill Switch recommendation emitted by HealthMonitor."""

    state: str
    reason: str
    runbook: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "reason": self.reason,
            "runbook": self.runbook,
        }


@dataclass(slots=True)
class HealthState:
    """Snapshot of health information shared with the CLI layer."""

    status: str = "ok"
    reasons: list[HealthReason] = field(default_factory=list)
    board_mode_suggestion: str | None = None
    board_mode_runbook: str | None = None
    kill_switch: KillSwitchSuggestion | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reasons": [reason.to_dict() for reason in self.reasons],
            "board_mode_suggestion": self.board_mode_suggestion,
            "board_mode_runbook": self.board_mode_runbook,
            "kill_switch": self.kill_switch.to_dict() if self.kill_switch else None,
        }


@dataclass(slots=True)
class HealthAction:
    """Queued health action that requires operator acknowledgement."""

    id: str
    action: str
    reason: str
    evidence: list[str] = field(default_factory=list)
    expires_at: datetime | None = None
    queued_at: datetime = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "reason": self.reason,
            "evidence": list(self.evidence),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "queued_at": self.queued_at.isoformat(),
        }


@dataclass(slots=True)
class GuardrailSnapshot:
    """Aggregated guardrail view combining health, gate, and kill switch signals."""

    health_status: str
    board_mode: str
    kill_switch_state: str
    spread_status: str
    reduce_only: bool
    exit_code: int
    reasons: list[str] = field(default_factory=list)
    banner: str | None = None
    runbook: str | None = None
    kill_switch_reason: str | None = None
    spread_reason: str | None = None
    reduce_only_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "health_status": self.health_status,
            "board_mode": self.board_mode,
            "kill_switch_state": self.kill_switch_state,
            "spread_status": self.spread_status,
            "reduce_only": self.reduce_only,
            "exit_code": self.exit_code,
            "reasons": list(self.reasons),
            "banner": self.banner,
            "runbook": self.runbook,
            "kill_switch_reason": self.kill_switch_reason,
            "spread_reason": self.spread_reason,
            "reduce_only_reason": self.reduce_only_reason,
        }


class HealthMonitor:
    """In-memory tracker for health status transitions.

    The monitor focuses on collecting the minimum state that the CLI must
    expose in M1: the current health status, board mode suggestions, and any
    Kill Switch recommendation that should be surfaced to operators.
    """

    _LEVEL_TO_STATUS = {
        "ok": "ok",
        "info": "ok",
        "warning": "warn",
        "degraded": "degraded",
        "soft_stop": "soft_stop",
        "critical": "soft_stop",
        "hard_stop": "hard_stop",
        "fatal": "hard_stop",
        "warn": "warn",
    }

    def __init__(self) -> None:
        self._state = HealthState()
        self._actions: list[HealthAction] = []

    def snapshot(self) -> HealthState:
        """Return a defensive copy of the current health state."""

        return copy.deepcopy(self._state)

    def to_dict(self) -> dict[str, Any]:
        return self._state.to_dict()

    def reasons(self) -> Iterable[HealthReason]:
        return tuple(self._state.reasons)

    def actions(self) -> Iterable[HealthAction]:
        return tuple(copy.deepcopy(self._actions))

    def raise_condition(
        self,
        level: str,
        reason: str,
        *,
        detail: str | None = None,
        recommended_action: str | None = None,
    ) -> None:
        """Register (or update) a degraded health reason."""

        mapped_status = self._LEVEL_TO_STATUS.get(level, "degraded")
        existing = next((r for r in self._state.reasons if r.code == reason), None)
        if existing is None:
            self._state.reasons.append(
                HealthReason(
                    code=reason,
                    level=level,
                    detail=detail,
                    recommended_action=recommended_action,
                )
            )
        else:
            existing.level = level
            existing.detail = detail
            existing.recommended_action = recommended_action
            existing.raised_at = _now()
        self._emit_health_event(level=level, reason=reason, detail=detail, action=recommended_action)

    def _emit_health_event(
        self,
        *,
        level: str,
        reason: str,
        detail: str | None,
        action: str | None,
    ) -> None:
        mapped_status = self._LEVEL_TO_STATUS.get(level, "degraded")
        runbook_ref = None
        if action and action.startswith("runbook:"):
            runbook_ref = action.split("runbook:", 1)[-1].strip() or None
        payload = {
            "event": "health.changed",
            "ts": _now().isoformat().replace("+00:00", "Z"),
            "level": level,
            "reason": reason,
            "detail": detail,
            "recommended_action": action,
        }
        if runbook_ref:
            payload["runbook_ref"] = runbook_ref
        try:
            DEFAULT_HEALTH_EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
            with DEFAULT_HEALTH_EVENT_LOG.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")
        except OSError:
            return
        self._state.status = self._merge_status(self._state.status, mapped_status)

    def queue_action(
        self,
        *,
        action: str,
        reason: str,
        evidence: Iterable[str] | None = None,
        expires_at: datetime | None = None,
        action_id: str | None = None,
    ) -> HealthAction:
        """Queue an action requiring operator acknowledgement."""

        action_id = action_id or f"{action}:{reason}"
        existing = next((item for item in self._actions if item.id == action_id), None)
        if existing is not None:
            return existing
        item = HealthAction(
            id=action_id,
            action=action,
            reason=reason,
            evidence=list(evidence or ()),
            expires_at=expires_at,
        )
        self._actions.append(item)
        return item

    def ack_action(self, action_id: str, *, actor: str = "cli") -> dict[str, Any]:
        """Acknowledge and remove a queued action if present."""

        remaining: list[HealthAction] = []
        acknowledged: HealthAction | None = None
        for item in self._actions:
            if item.id == action_id and acknowledged is None:
                acknowledged = item
                continue
            remaining.append(item)
        self._actions = remaining

        payload = {
            "action_id": action_id,
            "actor": actor,
            "ack_ts": _now().isoformat(),
        }
        if acknowledged:
            payload.update(
                {
                    "status": "acknowledged",
                    "reason": acknowledged.reason,
                    "action": acknowledged.action,
                    "evidence": acknowledged.evidence,
                }
            )
        else:
            payload["status"] = "not_found"
        return payload

    def clear(self, reason: str | None = None) -> None:
        """Clear a specific reason or reset the monitor entirely."""

        if reason is None:
            self._state = HealthState()
            self._actions = []
            return
        self._state.reasons = [r for r in self._state.reasons if r.code != reason]
        self._actions = [a for a in self._actions if a.reason != reason]
        if not self._state.reasons:
            self._state.status = "ok"
        else:
            self._state.status = self._recompute_status()

    def suggest_guarded(
        self,
        *,
        reason: str,
        runbook: str | None = None,
        gate_state: GateState | None = None,
        evidence: Iterable[str] | None = None,
        action_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        """Record a board mode suggestion for operators.

        Enforce auto-execute guard if provided.
        """

        self._state.board_mode_suggestion = reason
        self._state.board_mode_runbook = runbook
        self.queue_action(
            action="guarded",
            reason=reason,
            evidence=list(evidence or ()),
            action_id=action_id,
            expires_at=expires_at,
        )
        if gate_state is not None:
            self.enforce_auto_execute_policy(gate_state)

    def suggest_kill_switch(
        self,
        *,
        state: str,
        reason: str,
        runbook: str | None = None,
        gate_state: GateState | None = None,
    ) -> None:
        """Record a kill switch recommendation and guard auto-execute if provided."""

        self._state.kill_switch = KillSwitchSuggestion(
            state=state,
            reason=reason,
            runbook=runbook,
        )
        if gate_state is not None:
            gate_state.auto_execute = False

    def suggest_resume(
        self,
        *,
        reason: str,
        runbook: str | None = None,
        evidence: Iterable[str] | None = None,
        action_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        """Queue a resume suggestion once evidence has been gathered."""

        self._state.board_mode_suggestion = reason
        self._state.board_mode_runbook = runbook
        self.queue_action(
            action="resume",
            reason=reason,
            evidence=list(evidence or ()),
            action_id=action_id,
            expires_at=expires_at,
        )

    def _recompute_status(self) -> str:
        status = "ok"
        for reason in self._state.reasons:
            status = self._merge_status(status, self._LEVEL_TO_STATUS.get(reason.level, "degraded"))
        return status

    @staticmethod
    def _merge_status(current: str, incoming: str) -> str:
        try:
            current_idx = _SEVERITY_ORDER.index(current)
        except ValueError:
            current_idx = 0
        try:
            incoming_idx = _SEVERITY_ORDER.index(incoming)
        except ValueError:
            incoming_idx = 1
        return _SEVERITY_ORDER[max(current_idx, incoming_idx)]

    def enforce_auto_execute_policy(self, gate_state: GateState) -> None:
        """Apply board/health derived constraints to GateState.auto_execute."""

        if self._state.status in {"warn", "degraded", "soft_stop", "hard_stop"}:
            gate_state.auto_execute = False
            return
        suggestion = (self._state.board_mode_suggestion or "").lower()
        if suggestion in {"guarded", "halted", "halt"}:
            gate_state.auto_execute = False

    def _normalise_spread_state(self, state: str) -> str:
        if state in {"halt", "block"}:
            return "block"
        if state in {"watch", "cooldown"}:
            return "cooldown"
        return state

    def _compute_exit_code(
        self,
        *,
        health_status: str,
        kill_switch_state: str,
        spread_status: str,
        reduce_only: bool,
    ) -> int:
        if health_status == "hard_stop" or kill_switch_state == "hard_stop":
            return 63
        if kill_switch_state == "soft_stop":
            return 62
        if spread_status == "block":
            return 62
        if (
            spread_status == "cooldown"
            or reduce_only
            or health_status in {"warn", "degraded", "soft_stop"}
        ):
            return 21
        return 0

    def guardrail_snapshot(
        self,
        gate_state: GateState,
        *,
        kill_switch_state: str | None = None,
    ) -> GuardrailSnapshot:
        """Return the aggregated guardrail status for CLI consumption."""

        health = self.snapshot()
        spread_state = self._normalise_spread_state(gate_state.market.spread.state)
        spread_reason = gate_state.market.spread.reason

        kill_switch_reason = None
        if health.kill_switch:
            kill_switch_reason = health.kill_switch.reason
        if gate_state.risk.kill_switch_reason:
            kill_switch_reason = gate_state.risk.kill_switch_reason

        reduce_only_reason = gate_state.risk.reduce_only_reason

        effective_kill_switch = (
            kill_switch_state
            or (health.kill_switch.state if health.kill_switch else None)
            or gate_state.risk.kill_switch_recommendation
            or "none"
        )

        board_mode = "normal"
        if effective_kill_switch == "hard_stop" or health.status == "hard_stop":
            board_mode = "halted"
        elif (
            spread_state != "normal"
            or gate_state.risk.reduce_only
            or health.status in {"warn", "degraded", "soft_stop"}
        ):
            board_mode = "guarded"

        banner = (
            health.board_mode_suggestion
            or spread_reason
            or reduce_only_reason
            or kill_switch_reason
        )

        reasons: list[str] = [reason.code for reason in health.reasons]
        if spread_reason:
            reasons.append(f"spread:{spread_reason}")
        if reduce_only_reason:
            reasons.append(f"reduce_only:{reduce_only_reason}")
        if effective_kill_switch != "none":
            reasons.append(f"kill_switch:{effective_kill_switch}")

        exit_code = self._compute_exit_code(
            health_status=health.status,
            kill_switch_state=effective_kill_switch,
            spread_status=spread_state,
            reduce_only=gate_state.risk.reduce_only,
        )

        return GuardrailSnapshot(
            health_status=health.status,
            board_mode=board_mode,
            kill_switch_state=effective_kill_switch,
            spread_status=spread_state,
            reduce_only=gate_state.risk.reduce_only,
            exit_code=exit_code,
            reasons=reasons,
            banner=banner,
            runbook=health.board_mode_runbook,
            kill_switch_reason=kill_switch_reason,
            spread_reason=spread_reason,
            reduce_only_reason=reduce_only_reason,
        )


setattr(HealthMonitor, "raise", HealthMonitor.raise_condition)
