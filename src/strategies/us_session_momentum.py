"""US-session trend pullback strategy.

This strategy is intentionally separate from Donchian breakout logic.
It focuses on momentum re-acceleration after shallow pullbacks during
US hours.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from src.strategies.base import StrategyContext, StrategyMetadata, StrategyPluginProtocol


@dataclass(frozen=True, slots=True)
class UsMomentumSignal:
    strategy_id: str
    symbol: str
    direction: str
    confidence: float
    rationale: str
    score: float
    quality_score: float


class UsSessionTrendPullbackStrategy(StrategyPluginProtocol):
    """Trend pullback strategy constrained to US hours."""

    id = "m1_us_session_trend_pullback"
    determinism_key = "us_session_trend_pullback_v1"
    metadata = StrategyMetadata(
        name="M1 US Session Trend Pullback",
        version="0.1.0",
        required_features=frozenset(
            {
                "ema_fast_5m",
                "ema_slow_5m",
                "rsi_14_5m",
                "atr_14_1h",
                "ema55_slope_1h",
                "close_5m",
                "session_tag_5m",
                "regime_trend_1h",
            }
        ),
        tags=frozenset({"us_session", "momentum", "pullback"}),
    )
    context: StrategyContext | None = None

    def __init__(self, *, default_watchlist: Sequence[str] | None = None) -> None:
        self._default_watchlist = tuple(default_watchlist or ("USDJPY", "EURUSD", "GBPUSD"))

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
        except Exception:
            return None

    @staticmethod
    def _coerce_float(value: object, default: float) -> float:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _extract_map(value: object) -> Mapping[str, object]:
        if isinstance(value, Mapping):
            return value
        return {}

    def _entry_params(self, context: StrategyContext) -> Mapping[str, object]:
        params = self._extract_map(context.parameters)
        return self._extract_map(params.get("entry"))

    def _filter_params(self, context: StrategyContext) -> Mapping[str, object]:
        params = self._extract_map(context.parameters)
        entry = self._extract_map(params.get("entry"))
        nested = self._extract_map(entry.get("filters"))
        if nested:
            return nested
        return self._extract_map(params.get("filters"))

    def _execution_params(self, context: StrategyContext) -> Mapping[str, object]:
        params = self._extract_map(context.parameters)
        return self._extract_map(params.get("execution"))

    def _session_allowed(self, ts: object, session_range: str) -> bool:
        try:
            hour = ts.hour  # type: ignore[union-attr]
        except Exception:
            return True
        if "-" not in session_range:
            return True
        left, right = session_range.split("-", 1)
        try:
            start = int(left)
            end = int(right)
        except ValueError:
            return True
        if not (0 <= start <= 23 and 0 <= end <= 23):
            return True
        if start <= end:
            return start <= hour <= end
        return hour >= start or hour <= end

    @staticmethod
    def _blocked_hours(value: object) -> frozenset[int]:
        if value is None:
            return frozenset()
        values: list[int] = []
        if isinstance(value, (list, tuple, set, frozenset)):
            raw_items = list(value)
        elif isinstance(value, str):
            raw_items = [item.strip() for item in value.split(",")]
        else:
            raw_items = [value]
        for item in raw_items:
            try:
                hour = int(item)
            except (TypeError, ValueError):
                continue
            if 0 <= hour <= 23:
                values.append(hour)
        return frozenset(values)

    def _score_components(
        self,
        *,
        trend_gap: float,
        atr: float,
        slope: float,
        regime: float,
    ) -> tuple[float, float]:
        atr_norm = max(atr, 1e-6)
        gap_component = abs(trend_gap) / atr_norm
        slope_component = abs(slope) / atr_norm
        regime_component = abs(regime)
        quality_score = max(0.0, gap_component * 0.6 + slope_component * 0.25 + regime_component * 0.15)
        confidence = min(3.0, max(0.1, quality_score))
        return confidence, quality_score

    def generate_signals(self, context: StrategyContext) -> Iterable[UsMomentumSignal]:
        self.context = context
        if not self.metadata.required_features.issubset(context.features.available_keys):
            return []

        entry = self._entry_params(context)
        filters = self._filter_params(context)
        execution = self._execution_params(context)
        session_range = str(entry.get("session_utc_range", "16-23"))
        atr_min = self._coerce_float(filters.get("atr_min"), 0.0)
        trend_threshold = self._coerce_float(entry.get("trend_threshold"), 0.0)
        slope_min = self._coerce_float(entry.get("slope_min"), 0.0)
        rsi_long_min = self._coerce_float(entry.get("rsi_long_min"), 48.0)
        rsi_long_max = self._coerce_float(entry.get("rsi_long_max"), 64.0)
        rsi_short_min = self._coerce_float(entry.get("rsi_short_min"), 36.0)
        rsi_short_max = self._coerce_float(entry.get("rsi_short_max"), 52.0)
        spread_limit = self._coerce_float(filters.get("spread_max"), -1.0)
        spread = self._coerce_float(execution.get("spread"), 0.0)
        blocked_hours = self._blocked_hours(
            entry.get("blocked_utc_hours", filters.get("blocked_utc_hours"))
        )

        symbols = sorted(context.watchlist or frozenset(self._default_watchlist))
        signals: list[UsMomentumSignal] = []
        current_hour_raw = getattr(context.clock.now, "hour", None)
        current_hour = int(current_hour_raw) if isinstance(current_hour_raw, (int, float)) else None
        for symbol in symbols:
            if not self._session_allowed(context.clock.now, session_range):
                continue
            if current_hour is not None and current_hour in blocked_hours:
                continue
            if spread_limit >= 0 and spread > spread_limit:
                continue

            try:
                ema_fast = self._latest(
                    context.features.lookup(symbol=symbol, feature="ema_fast_5m", timeframe="5m")
                )
                ema_slow = self._latest(
                    context.features.lookup(symbol=symbol, feature="ema_slow_5m", timeframe="5m")
                )
                rsi = self._latest(
                    context.features.lookup(symbol=symbol, feature="rsi_14_5m", timeframe="5m")
                )
                atr = self._latest(
                    context.features.lookup(symbol=symbol, feature="atr_14_1h", timeframe="1h")
                )
                slope = self._latest(
                    context.features.lookup(symbol=symbol, feature="ema55_slope_1h", timeframe="1h")
                )
                close = self._latest(
                    context.features.lookup(symbol=symbol, feature="close_5m", timeframe="5m")
                )
                regime = self._latest(
                    context.features.lookup(
                        symbol=symbol, feature="regime_trend_1h", timeframe="1h"
                    )
                )
            except Exception:
                continue

            if (
                ema_fast is None
                or ema_slow is None
                or rsi is None
                or atr is None
                or slope is None
                or close is None
                or regime is None
            ):
                continue
            if atr < atr_min:
                continue

            trend_gap = ema_fast - ema_slow
            long_bias = (
                regime > trend_threshold
                and trend_gap > 0
                and slope > slope_min
                and rsi_long_min <= rsi <= rsi_long_max
                and close >= ema_fast
            )
            short_bias = (
                regime < -trend_threshold
                and trend_gap < 0
                and slope < -slope_min
                and rsi_short_min <= rsi <= rsi_short_max
                and close <= ema_fast
            )
            if not long_bias and not short_bias:
                continue

            direction = "long" if long_bias else "short"
            confidence, quality = self._score_components(
                trend_gap=trend_gap,
                atr=atr,
                slope=slope,
                regime=regime,
            )
            signals.append(
                UsMomentumSignal(
                    strategy_id=self.id,
                    symbol=symbol,
                    direction=direction,
                    confidence=round(confidence, 4),
                    rationale="us_session_pullback_resume",
                    score=round(quality, 4),
                    quality_score=round(quality, 4),
                )
            )
        return signals

    def required_warmup_bars(self) -> int:
        return 200

    def cooldown_bars(self) -> int:
        return 3

    def evaluate(self, context: StrategyContext) -> Iterable[UsMomentumSignal]:
        return self.generate_signals(context)


__all__ = ["UsSessionTrendPullbackStrategy", "UsMomentumSignal"]
