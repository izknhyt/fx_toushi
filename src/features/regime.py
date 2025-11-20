"""Regime detector scaffold described in §1.3."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class RegimeSnapshot:
    """Represents the inferred market regime."""

    mode: str
    volatility: float
    trend_score: float


class RegimeDetector:
    """Classifies a price series into trending/ranging modes."""

    def classify(self, prices: pd.Series) -> RegimeSnapshot:
        if prices.empty:
            return RegimeSnapshot(mode="unknown", volatility=0.0, trend_score=0.0)
        returns = prices.pct_change().dropna()
        volatility = float(returns.std(ddof=0)) if not returns.empty else 0.0
        trend = float(prices.rolling(window=50, min_periods=25).mean().iloc[-1] - prices.iloc[-1])
        trend_score = -trend
        mode = "trending" if abs(trend_score) > 0.5 * (volatility + 1e-6) else "ranging"
        return RegimeSnapshot(mode=mode, volatility=volatility, trend_score=trend_score)


__all__ = ["RegimeDetector", "RegimeSnapshot"]
