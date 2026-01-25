"""Sequential Probability Ratio Test utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


@dataclass(slots=True)
class SprtResult:
    stop: bool
    reason: str | None = None
    llr: float = 0.0
    samples: int = 0


@dataclass(slots=True)
class SprtState:
    llr: float = 0.0
    samples: int = 0
    stopped_at: datetime | None = None
    last_reason: str | None = None

    @property
    def stopped(self) -> bool:
        return self.stopped_at is not None


class SprtEvaluator:
    def __init__(
        self,
        *,
        alpha: float = 0.05,
        beta: float = 0.1,
        p0: float = 0.5,
        p1: float = 0.6,
    ) -> None:
        self.alpha = alpha
        self.beta = beta
        self.p0 = p0
        self.p1 = p1
        self._log_a = math.log((1 - beta) / alpha)
        self._log_b = math.log(beta / (1 - alpha))

    def evaluate(
        self,
        outcomes: Iterable[bool | int | float],
        *,
        state: SprtState | None = None,
    ) -> SprtResult:
        current = state or SprtState()
        for outcome in outcomes:
            current.llr += _log_likelihood_ratio(outcome, p0=self.p0, p1=self.p1)
            current.samples += 1
            if current.llr >= self._log_a:
                current.last_reason = "accept"
                return SprtResult(stop=True, reason="accept", llr=current.llr, samples=current.samples)
            if current.llr <= self._log_b:
                current.last_reason = "reject"
                return SprtResult(stop=True, reason="reject", llr=current.llr, samples=current.samples)
        return SprtResult(stop=False, llr=current.llr, samples=current.samples)


class SprtStateMachine:
    def __init__(
        self,
        *,
        evaluator: SprtEvaluator | None = None,
        cooldown_hours: int = 24,
    ) -> None:
        self._evaluator = evaluator or SprtEvaluator()
        self._cooldown = timedelta(hours=cooldown_hours)
        self._state = SprtState()

    @property
    def state(self) -> SprtState:
        return self._state

    def evaluate(self, outcomes: Iterable[bool | int | float]) -> SprtResult:
        if self._state.stopped:
            return SprtResult(
                stop=True,
                reason=self._state.last_reason or "cooldown",
                llr=self._state.llr,
                samples=self._state.samples,
            )
        result = self._evaluator.evaluate(outcomes, state=self._state)
        if result.stop:
            self._state.stopped_at = _utcnow()
            self._state.last_reason = result.reason
        return result

    def try_resume(self, *, now: datetime | None = None) -> bool:
        if not self._state.stopped:
            return True
        current = now or _utcnow()
        if current - self._state.stopped_at >= self._cooldown:
            self._state = SprtState()
            return True
        return False


def _log_likelihood_ratio(outcome: bool | int | float, *, p0: float, p1: float) -> float:
    value = _normalize_outcome(outcome)
    if value == 1:
        return math.log(p1 / p0)
    return math.log((1 - p1) / (1 - p0))


def _normalize_outcome(outcome: bool | int | float) -> int:
    if isinstance(outcome, bool):
        return int(outcome)
    if isinstance(outcome, int):
        if outcome in (0, 1):
            return outcome
    if isinstance(outcome, float):
        if 0.0 <= outcome <= 1.0:
            return 1 if outcome >= 0.5 else 0
    raise ValueError(f"Unsupported outcome value: {outcome}")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


__all__ = ["SprtEvaluator", "SprtResult", "SprtState", "SprtStateMachine"]
