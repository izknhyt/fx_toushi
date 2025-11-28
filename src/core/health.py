"""Lightweight health state management primitives used by the CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import copy
from typing import TYPE_CHECKING, Any, Dict, Iterable

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from src.core.gate import GateState

__all__ = [
    "HealthMonitor",
    "HealthReason",
    "HealthState",
    "KillSwitchSuggestion",
]


_SEVERITY_ORDER = ("ok", "degraded", "soft_stop", "hard_stop")


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

    def to_dict(self) -> Dict[str, Any]:
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

    def to_dict(self) -> Dict[str, Any]:
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reasons": [reason.to_dict() for reason in self.reasons],
            "board_mode_suggestion": self.board_mode_suggestion,
            "board_mode_runbook": self.board_mode_runbook,
            "kill_switch": self.kill_switch.to_dict() if self.kill_switch else None,
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
        "warning": "degraded",
        "degraded": "degraded",
        "soft_stop": "soft_stop",
        "critical": "soft_stop",
        "hard_stop": "hard_stop",
        "fatal": "hard_stop",
    }

    def __init__(self) -> None:
        self._state = HealthState()

    def snapshot(self) -> HealthState:
        """Return a defensive copy of the current health state."""

        return copy.deepcopy(self._state)

    def to_dict(self) -> Dict[str, Any]:
        return self._state.to_dict()

    def reasons(self) -> Iterable[HealthReason]:
        return tuple(self._state.reasons)

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
        self._state.status = self._merge_status(self._state.status, mapped_status)

    def clear(self, reason: str | None = None) -> None:
        """Clear a specific reason or reset the monitor entirely."""

        if reason is None:
            self._state = HealthState()
            return
        self._state.reasons = [r for r in self._state.reasons if r.code != reason]
        if not self._state.reasons:
            self._state.status = "ok"
        else:
            self._state.status = self._recompute_status()

    def suggest_guarded(self, *, reason: str, runbook: str | None = None, gate_state: "GateState" | None = None) -> None:
        """Record a board mode suggestion for operators and enforce auto-execute guard if provided."""

        self._state.board_mode_suggestion = reason
        self._state.board_mode_runbook = runbook
        if gate_state is not None:
            self.enforce_auto_execute_policy(gate_state)

    def suggest_kill_switch(
        self,
        *,
        state: str,
        reason: str,
        runbook: str | None = None,
        gate_state: "GateState" | None = None,
    ) -> None:
        """Record a kill switch recommendation and guard auto-execute if provided."""

        self._state.kill_switch = KillSwitchSuggestion(
            state=state,
            reason=reason,
            runbook=runbook,
        )
        if gate_state is not None:
            gate_state.auto_execute = False

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

    def enforce_auto_execute_policy(self, gate_state: "GateState") -> None:
        """Apply board/health derived constraints to GateState.auto_execute."""

        if self._state.status in {"degraded", "soft_stop", "hard_stop"}:
            gate_state.auto_execute = False
            return
        suggestion = (self._state.board_mode_suggestion or "").lower()
        if suggestion in {"guarded", "halted", "halt"}:
            gate_state.auto_execute = False


setattr(HealthMonitor, "raise", HealthMonitor.raise_condition)
