"""Lightweight RateLimitGuard for provider polling stages (see §7.6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(slots=True)
class StageDecision:
    provider: str
    stage: str
    decision: str
    tokens_remaining: float
    sample_window_min: int
    rate_429: float
    max_concurrent: int
    poll_interval_sec: float
    decision_source: str | None = None
    runbook_ref: str | None = None

    def to_mapping(self) -> Mapping[str, object]:
        return {
            "provider": self.provider,
            "stage": self.stage,
            "decision": self.decision,
            "tokens_remaining": self.tokens_remaining,
            "sample_window_min": self.sample_window_min,
            "429_rate": self.rate_429,
            "max_concurrent": self.max_concurrent,
            "poll_interval_sec": self.poll_interval_sec,
            "decision_source": self.decision_source,
            "runbook_ref": self.runbook_ref,
        }


class RateLimitGuard:
    """Stateless stage evaluator based on rolling 429 rate and token bucket."""

    def __init__(self, *, tokens_per_minute: float, burst_tokens: float, poll_interval_sec: float, stages: list[str]) -> None:
        self.tokens_per_minute = tokens_per_minute
        self.burst_tokens = burst_tokens
        self.poll_interval_sec = poll_interval_sec
        self.stages = stages or ["stage0"]

    def evaluate(
        self,
        *,
        provider: str,
        rate_429: float,
        current_stage: str | None = None,
        decision_source: str | None = None,
        runbook_ref: str | None = None,
    ) -> StageDecision:
        stage = current_stage or (self.stages[0])
        decision = "hold"
        idx = self.stages.index(stage) if stage in self.stages else 0
        next_stage = self.stages[min(idx + 1, len(self.stages) - 1)]
        prev_stage = self.stages[max(idx - 1, 0)]

        if rate_429 <= 0.01 and idx < len(self.stages) - 1:
            stage = next_stage
            decision = "promote"
        elif rate_429 > 0.015 and idx > 0:
            stage = prev_stage
            decision = "rollback"

        tokens_remaining = min(self.burst_tokens, self.tokens_per_minute)
        poll_interval = self._poll_interval(stage)
        max_concurrent = self._max_concurrent(tokens_remaining, poll_interval)
        return StageDecision(
            provider=provider,
            stage=stage,
            decision=decision,
            tokens_remaining=tokens_remaining,
            sample_window_min=60,
            rate_429=rate_429,
            max_concurrent=max_concurrent,
            poll_interval_sec=poll_interval,
            decision_source=decision_source,
            runbook_ref=runbook_ref,
        )

    def _max_concurrent(self, tokens_remaining: float, poll_interval: float) -> int:
        per_min_slot = max(poll_interval, 1)
        slots_per_min = 60 / per_min_slot
        return int(tokens_remaining / slots_per_min) if slots_per_min else 1

    def _poll_interval(self, stage: str) -> float:
        idx = self.stages.index(stage) if stage in self.stages else 0
        # shorten interval slightly on higher stages
        return max(self.poll_interval_sec - idx * 1.5, 3.0)

    def worker_plan(self, *, provider: str, stage: str | None = None) -> Mapping[str, object]:
        """Return polling interval and max workers for the given stage."""

        effective_stage = stage or (self.stages[0])
        poll_interval = self._poll_interval(effective_stage)
        max_workers = self._max_concurrent(self.burst_tokens, poll_interval)
        return {
            "provider": provider,
            "stage": effective_stage,
            "poll_interval_sec": poll_interval,
            "max_workers": max_workers,
        }


__all__ = ["RateLimitGuard", "StageDecision"]
