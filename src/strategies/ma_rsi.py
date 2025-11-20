"""MA+RSI baseline strategy plugin declared in §1.3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from src.strategies.base import StrategyContext, StrategyMetadata, StrategyPluginProtocol


@dataclass(frozen=True, slots=True)
class StrategySignal:
    """Simple RawSignal implementation."""

    strategy_id: str
    symbol: str
    direction: str
    confidence: float
    rationale: str


class MovingAverageRsiStrategy(StrategyPluginProtocol):
    """Deterministic MA+RSI strategy used for scaffolding tests."""

    id = "m1_baseline_ma_rsi"
    determinism_key = "ma_rsi_v1"
    metadata = StrategyMetadata(
        name="MA+RSI Baseline",
        version="1.0.0",
        required_features=frozenset({"close_ma_fast", "close_ma_slow", "close_rsi"}),
        tags=frozenset({"baseline", "hitl"}),
    )
    context: StrategyContext | None = None

    def __init__(self, *, default_watchlist: Sequence[str] | None = None) -> None:
        self._default_watchlist = tuple(default_watchlist or ("USDJPY", "EURUSD"))

    def generate_signals(self, context: StrategyContext) -> Iterable[StrategySignal]:
        self.context = context
        required = self.metadata.required_features
        if not required.issubset(context.features.available_keys):
            return []

        symbols = sorted(context.watchlist or frozenset(self._default_watchlist))
        signals: list[StrategySignal] = []
        for index, symbol in enumerate(symbols):
            score = ((context.seed + index) % 100) / 100
            if score < 0.35:
                continue
            direction = "long" if index % 2 == 0 else "short"
            signals.append(
                StrategySignal(
                    strategy_id=self.id,
                    symbol=symbol,
                    direction=direction,
                    confidence=round(score, 4),
                    rationale="ma_rsi_alignment",
                )
            )
        return signals

    def required_warmup_bars(self) -> int:
        return 250

    def cooldown_bars(self) -> int:
        return 3

    def evaluate(self, context: StrategyContext) -> Iterable[StrategySignal]:
        return self.generate_signals(context)


__all__ = ["MovingAverageRsiStrategy", "StrategySignal"]
