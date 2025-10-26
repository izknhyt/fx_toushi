"""Strategy engine base contracts.

This module surfaces the interfaces that strategy plugins conform to so
that Codex can reason about deterministic signal generation. The
structures here intentionally avoid business logic and instead document
expectations that downstream registries and pipelines will enforce.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence, runtime_checkable


@dataclass(slots=True)
class StrategyContext:
    """Shared services handed to strategy plugins.

    Context objects encapsulate feature frames, gate states, and data
    accessors in a way that supports deterministic replay.
    """

    feature_frame: Mapping[str, float]
    gate_state: Mapping[str, str]
    metadata: Mapping[str, str]


@dataclass(slots=True)
class StrategySignal:
    """Normalized output of a strategy plugin.

    The signal structure is intentionally simple for M1. Additional
    metrics (confidence, regime tags) will be attached under dedicated
    feature flags in later milestones.
    """

    symbol: str
    action: str
    score: float


@runtime_checkable
class Strategy(Protocol):
    """Protocol that every strategy plugin must satisfy."""

    name: str
    required_features: Sequence[str]

    def generate(self, context: StrategyContext) -> Sequence[StrategySignal]:
        """Produce one or more signals for the provided context."""
