"""Canonical candidate trade payload for portfolio-first evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CandidateTrade:
    candidate_id: str
    strategy_id: str
    symbol: str
    side: str
    timestamp: str
    entry: float | None
    stop: float | None
    target: float | None
    confidence: float | None
    expected_holding_minutes: float | None
    portfolio_group: str
    exposure_bucket: str
    expected_edge: float | None = None
    estimated_cost: float | None = None
    quality_score: float | None = None
    regime_fit: float | None = None
    session_tag: str | None = None
    atr_value: float | None = None
    trend_value: float | None = None
    cost_ratio: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "side": self.side,
            "timestamp": self.timestamp,
            "entry": self.entry,
            "stop": self.stop,
            "target": self.target,
            "confidence": self.confidence,
            "expected_holding_minutes": self.expected_holding_minutes,
            "portfolio_group": self.portfolio_group or None,
            "exposure_bucket": self.exposure_bucket or None,
            "expected_edge": self.expected_edge,
            "estimated_cost": self.estimated_cost,
            "quality_score": self.quality_score,
            "regime_fit": self.regime_fit,
            "session_tag": self.session_tag,
            "atr_value": self.atr_value,
            "trend_value": self.trend_value,
            "cost_ratio": self.cost_ratio,
            "metadata": dict(self.metadata),
        }
