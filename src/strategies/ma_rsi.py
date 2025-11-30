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
    rsi_long_threshold = 55
    rsi_short_threshold = 45
    min_gap_pct = 0.0005
    slope_min = 0.0
    metadata = StrategyMetadata(
        name="M1 Baseline MA/RSI",
        version="0.1.1",
        required_features=frozenset(
            {
                "ema_fast_5m",
                "ema_slow_5m",
                "rsi_14_5m",
                "atr_14_1h",
                "ema55_slope_1h",
                "session_tag_5m",
                "regime_trend_1h",
                "close_5m",
            }
        ),
        tags=frozenset({"baseline", "hitl"}),
    )
    context: StrategyContext | None = None

    def __init__(self, *, default_watchlist: Sequence[str] | None = None) -> None:
        self._default_watchlist = tuple(default_watchlist or ("USDJPY", "EURUSD"))

    @staticmethod
    def _latest(value: object) -> float | None:
        """Return the latest scalar from a feature payload."""

        if value is None:
            return None
        if isinstance(value, (float, int)):
            return float(value)
        # pandas Series/DataFrame-like objects
        getter = getattr(value, "iloc", None)
        if getter is not None:
            try:
                return float(value.iloc[-1])
            except Exception:
                pass
        try:
            return float(value)
        except Exception:  # pragma: no cover - defensive
            return None

    def _extract_features(
        self, context: StrategyContext, symbol: str
    ) -> tuple[float | None, float | None, float | None, float | None, float | None, float | None, float | None]:
        features = context.features
        try:
            fast = features.lookup(symbol=symbol, feature="ema_fast_5m", timeframe="5m")
            slow = features.lookup(symbol=symbol, feature="ema_slow_5m", timeframe="5m")
            rsi = features.lookup(symbol=symbol, feature="rsi_14_5m", timeframe="5m")
            atr = features.lookup(symbol=symbol, feature="atr_14_1h", timeframe="1h")
            slope = features.lookup(symbol=symbol, feature="ema55_slope_1h", timeframe="1h")
            close = features.lookup(symbol=symbol, feature="close_5m", timeframe="5m")
            regime = features.lookup(symbol=symbol, feature="regime_trend_1h", timeframe="1h")
        except Exception:
            return None, None, None, None, None, None, None
        return (
            self._latest(fast),
            self._latest(slow),
            self._latest(rsi),
            self._latest(atr),
            self._latest(slope),
            self._latest(close),
            self._latest(regime),
        )

    def _session_allowed(self, ts: object) -> bool:
        """Gate trades to liquid hours (06:00–21:59 UTC)."""

        try:
            hour = ts.hour  # type: ignore[union-attr]
        except Exception:
            return True
        return 6 <= hour <= 21

    def generate_signals(self, context: StrategyContext) -> Iterable[StrategySignal]:
        self.context = context
        if not self.metadata.required_features.issubset(context.features.available_keys):
            return []

        symbols = sorted(context.watchlist or frozenset(self._default_watchlist))
        signals: list[StrategySignal] = []
        for index, symbol in enumerate(symbols):
            fast, slow, rsi, atr, slope, close, regime = self._extract_features(context, symbol)
            if fast is None or slow is None or rsi is None or atr is None or close is None or regime is None:
                continue
            if not self._session_allowed(context.clock.now):
                continue
            trend_bias = fast - slow
            min_gap = abs(close) * self.min_gap_pct
            direction: str | None = None
            slope_v = slope or 0.0
            if rsi <= self.rsi_short_threshold and trend_bias < -min_gap and slope_v < -self.slope_min and regime < 0:
                direction = "short"
            elif rsi >= self.rsi_long_threshold and trend_bias > min_gap and slope_v > self.slope_min and regime > 0:
                direction = "long"
            else:
                continue

            slope_hint = slope_v if slope is not None else trend_bias
            confidence = min(max(abs(slope_hint) / max(atr, 1e-6), 0.1), 3.0)
            signals.append(
                StrategySignal(
                    strategy_id=self.id,
                    symbol=symbol,
                    direction=direction,
                    confidence=round(float(confidence), 4),
                    rationale="ma_rsi_alignment",
                )
            )
        return signals

    def required_warmup_bars(self) -> int:
        return 250

    def cooldown_bars(self) -> int:
        return getattr(self, "_cooldown_bars", 4)

    def evaluate(self, context: StrategyContext) -> Iterable[StrategySignal]:
        return self.generate_signals(context)


__all__ = ["MovingAverageRsiStrategy", "StrategySignal"]
