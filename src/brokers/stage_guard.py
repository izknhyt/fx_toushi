"""Autonomy stage guard with monotonic promotion and rollback on circuit events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, List


StageName = Literal["manual", "paper_live_bridge", "live_shadow", "live"]


@dataclass(slots=True)
class StageTransition:
    """Record of a stage transition for audit/history."""

    from_stage: StageName
    to_stage: StageName
    actor: str
    reason: str | None
    ts: datetime


class AutonomyStageGuard:
    """Minimal stage guard managing paper_live_bridge -> live_shadow -> live transitions."""

    _allowed_order: tuple[StageName, ...] = ("manual", "paper_live_bridge", "live_shadow", "live")

    def __init__(self, stage: StageName = "manual") -> None:
        self.stage: StageName = stage
        self._history: List[StageTransition] = []

    def promote(self, stage: StageName, *, actor: str = "system", reason: str | None = None) -> StageTransition:
        """Promote to the requested stage if it respects the monotonic ordering."""

        current_index = self._allowed_order.index(self.stage)
        target_index = self._allowed_order.index(stage)
        if target_index < current_index:
            raise ValueError(f"Cannot demote from {self.stage} to {stage}")
        transition = StageTransition(from_stage=self.stage, to_stage=stage, actor=actor, reason=reason, ts=datetime.utcnow())
        self.stage = stage
        self._history.append(transition)
        return transition

    def rollback_one(self, *, actor: str = "system", reason: str | None = None) -> StageTransition | None:
        """Rollback one stage (circuit breaker) if possible."""

        current_index = self._allowed_order.index(self.stage)
        if current_index == 0:
            return None
        target_stage = self._allowed_order[current_index - 1]
        transition = StageTransition(from_stage=self.stage, to_stage=target_stage, actor=actor, reason=reason, ts=datetime.utcnow())
        self.stage = target_stage
        self._history.append(transition)
        return transition

    def on_error(self, error_class: str, *, actor: str = "system", reason: str | None = None) -> StageTransition | None:
        """Handle error classification: circuit_breaker triggers a rollback."""

        if error_class == "circuit_breaker":
            return self.rollback_one(actor=actor, reason=reason or "circuit_breaker")
        return None

    def recover(self, *, actor: str = "system", reason: str | None = None) -> StageTransition | None:
        """Promote one step after a circuit breaker resolution."""

        current_index = self._allowed_order.index(self.stage)
        if current_index + 1 >= len(self._allowed_order):
            return None
        target_stage = self._allowed_order[current_index + 1]
        transition = StageTransition(from_stage=self.stage, to_stage=target_stage, actor=actor, reason=reason, ts=datetime.utcnow())
        self.stage = target_stage
        self._history.append(transition)
        return transition

    def history(self) -> list[StageTransition]:
        return list(self._history)


__all__ = ["AutonomyStageGuard"]
