"""Donchian breakout strategy stub described in §1.3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from src.strategies.base import StrategyContext, StrategyMetadata, StrategyPluginProtocol


@dataclass(frozen=True, slots=True)
class BreakoutSignal:
    strategy_id: str
    symbol: str
    breakout: str
    level: float | None


class DonchianBreakoutStrategy(StrategyPluginProtocol):
    """Generates deterministic breakout alerts per symbol."""

    id = "m1_baseline_donchian"
    determinism_key = "donchian_v1"
    metadata = StrategyMetadata(
        name="Donchian Breakout",
        version="1.0.0",
        required_features=frozenset({"donchian_upper", "donchian_lower"}),
        tags=frozenset({"baseline", "breakout"}),
    )
    context: StrategyContext | None = None

    def __init__(self, *, default_watchlist: Sequence[str] | None = None) -> None:
        self._default_watchlist = tuple(default_watchlist or ("GBPJPY", "AUDUSD"))

    def generate_signals(self, context: StrategyContext) -> Iterable[BreakoutSignal]:
        self.context = context
        if not self.metadata.required_features.issubset(context.features.available_keys):
            return []

        symbols = sorted(context.watchlist or frozenset(self._default_watchlist))
        signals: list[BreakoutSignal] = []
        for index, symbol in enumerate(symbols):
            roll = (context.seed + index) % 3
            if roll == 0:
                continue
            breakout = "upper" if roll == 1 else "lower"
            signals.append(
                BreakoutSignal(
                    strategy_id=self.id,
                    symbol=symbol,
                    breakout=breakout,
                    level=None,
                )
            )
        return signals

    def required_warmup_bars(self) -> int:
        return 120

    def cooldown_bars(self) -> int:
        return 2

    def evaluate(self, context: StrategyContext) -> Iterable[BreakoutSignal]:
        return self.generate_signals(context)


__all__ = ["DonchianBreakoutStrategy", "BreakoutSignal"]
