"""Donchian breakout strategy stub described in §1.3."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from src.features.pipeline import FeatureLookupError
from src.strategies.base import StrategyContext, StrategyMetadata, StrategyPluginProtocol


@dataclass(frozen=True, slots=True)
class BreakoutSignal:
    strategy_id: str
    symbol: str
    breakout: str
    level: float | None
    buffer: float | None
    rationale: str


class DonchianBreakoutStrategy(StrategyPluginProtocol):
    """Deterministic Donchian breakout strategy aligned with the design."""

    id = "m1_baseline_donchian"
    determinism_key = "donchian_v1"
    metadata = StrategyMetadata(
        name="M1 Baseline Donchian",
        version="0.1.2",
        required_features=frozenset(
            {
                "donchian_upper20_1h",
                "donchian_lower20_1h",
                "donchian_mid20_1h",
                "donchian_upper20_1d",
                "donchian_lower20_1d",
                "donchian_mid20_1d",
                "atr_14_1h",
                "close_5m",
                "regime_trend_1h",
                "session_tag_5m",
            }
        ),
        tags=frozenset({"baseline", "breakout"}),
    )
    context: StrategyContext | None = None

    def __init__(self, *, default_watchlist: Sequence[str] | None = None) -> None:
        self._default_watchlist = tuple(
            default_watchlist or ("USDJPY", "EURUSD", "GBPUSD", "EURJPY", "AUDUSD")
        )

    @staticmethod
    def _latest(value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        getter = getattr(value, "iloc", None)
        if getter is not None:
            try:
                return float(value.iloc[-1])
            except Exception:
                return None
        try:
            return float(value)
        except Exception:  # pragma: no cover - defensive
            return None

    def _session_allowed(self, ts: object) -> bool:
        try:
            hour = ts.hour  # type: ignore[union-attr]
        except Exception:
            return True
        return 6 <= hour <= 21

    def generate_signals(self, context: StrategyContext) -> Iterable[BreakoutSignal]:
        self.context = context
        if not self.metadata.required_features.issubset(context.features.available_keys):
            return []

        symbols = sorted(context.watchlist or frozenset(self._default_watchlist))
        signals: list[BreakoutSignal] = []
        for _index, symbol in enumerate(symbols):
            if not self._session_allowed(context.clock.now):
                continue
            try:
                upper_h = context.features.lookup(
                    symbol=symbol, feature="donchian_upper20_1h", timeframe="1h"
                )
                lower_h = context.features.lookup(
                    symbol=symbol, feature="donchian_lower20_1h", timeframe="1h"
                )
                mid_h = context.features.lookup(
                    symbol=symbol, feature="donchian_mid20_1h", timeframe="1h"
                )
                close = context.features.lookup(symbol=symbol, feature="close_5m", timeframe="5m")
                atr = context.features.lookup(symbol=symbol, feature="atr_14_1h", timeframe="1h")
            except Exception:
                continue
            try:
                upper_d = context.features.lookup(
                    symbol=symbol, feature="donchian_upper20_1d", timeframe="1d"
                )
                lower_d = context.features.lookup(
                    symbol=symbol, feature="donchian_lower20_1d", timeframe="1d"
                )
                mid_d = context.features.lookup(
                    symbol=symbol, feature="donchian_mid20_1d", timeframe="1d"
                )
            except FeatureLookupError:
                upper_d = lower_d = mid_d = None

            # prefer 1h bands; fall back to 1d
            upper_v = self._latest(upper_h) or self._latest(upper_d)
            lower_v = self._latest(lower_h) or self._latest(lower_d)
            mid_v = self._latest(mid_h) or self._latest(mid_d)
            close_v = self._latest(close)
            atr_v = self._latest(atr)
            if upper_v is None or lower_v is None or close_v is None or atr_v is None:
                continue

            buffer = max(0.05, atr_v * 0.02)
            breakout: str | None = None
            level = None
            rationale = ""
            if close_v > upper_v + buffer:
                breakout = "upper"
                level = upper_v
                rationale = "breakout_upper"
            elif close_v < lower_v - buffer:
                breakout = "lower"
                level = lower_v
                rationale = "breakout_lower"
            elif abs(close_v - mid_v) <= atr_v * 0.1:
                # avoid mid-chop
                continue
            else:
                continue

            signals.append(
                BreakoutSignal(
                    strategy_id=self.id,
                    symbol=symbol,
                    breakout=breakout,
                    level=level,
                    buffer=buffer,
                    rationale=rationale,
                )
            )
        return signals

    def required_warmup_bars(self) -> int:
        return 120

    def cooldown_bars(self) -> int:
        return 3

    def evaluate(self, context: StrategyContext) -> Iterable[BreakoutSignal]:
        return self.generate_signals(context)


__all__ = ["DonchianBreakoutStrategy", "BreakoutSignal"]
