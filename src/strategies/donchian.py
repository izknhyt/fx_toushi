"""Donchian breakout strategy stub described in §1.3."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from src.features.pipeline import FeatureLookupError
from src.strategies.base import StrategyContext, StrategyMetadata, StrategyPluginProtocol


@dataclass(frozen=True, slots=True)
class BreakoutSignal:
    strategy_id: str
    symbol: str
    direction: str
    breakout: str
    level: float | None
    buffer: float | None
    rationale: str
    breakout_width: float | None = None
    filter_flags: Mapping[str, bool] | None = None
    filter_block_reason: str | None = None
    quality_score: float | None = None


class _BaseDonchianBreakoutStrategy(StrategyPluginProtocol):
    """Shared Donchian breakout logic with configurable direction mode."""

    mode: str = "bidirectional"
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

    def _parse_session_range(self, filters: Mapping[str, object]) -> tuple[int, int]:
        session_value = filters.get("session_utc_range")
        if not isinstance(session_value, str):
            return (6, 21)
        text = session_value.strip()
        if not text:
            return (6, 21)
        parts = text.split("-")
        if len(parts) != 2:
            return (6, 21)
        try:
            start = int(parts[0])
            end = int(parts[1])
        except ValueError:
            return (6, 21)
        if not (0 <= start <= 23 and 0 <= end <= 23):
            return (6, 21)
        return (start, end)

    def _session_allowed(self, ts: object, filters: Mapping[str, object]) -> bool:
        try:
            hour = ts.hour  # type: ignore[union-attr]
        except Exception:
            return True
        start, end = self._parse_session_range(filters)
        if start <= end:
            return start <= hour <= end
        return hour >= start or hour <= end

    def _resolve_direction(self, breakout: str) -> str | None:
        if self.mode == "upper_only":
            return "long" if breakout == "upper" else None
        if self.mode == "long_only":
            return "long"
        return "long" if breakout == "upper" else "short"

    @staticmethod
    def _coerce_float(value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except Exception:
            return None

    def _extract_filters(self, context: StrategyContext) -> Mapping[str, object]:
        params = context.parameters if isinstance(context.parameters, Mapping) else {}
        entry = params.get("entry") if isinstance(params, Mapping) else {}
        if isinstance(entry, Mapping) and "filters" in entry:
            nested_filters = entry.get("filters")
            if isinstance(nested_filters, Mapping):
                return nested_filters
        # Compatibility fallback for existing manifest layout: parameters.filters
        root_filters = params.get("filters") if isinstance(params, Mapping) else {}
        if isinstance(root_filters, Mapping):
            return root_filters
        return {}

    def _extract_execution(self, context: StrategyContext) -> Mapping[str, object]:
        params = context.parameters if isinstance(context.parameters, Mapping) else {}
        execution = params.get("execution") if isinstance(params, Mapping) else {}
        if isinstance(execution, Mapping):
            return execution
        return {}

    def generate_signals(self, context: StrategyContext) -> Iterable[BreakoutSignal]:
        self.context = context
        if not self.metadata.required_features.issubset(context.features.available_keys):
            return []

        symbols = sorted(context.watchlist or frozenset(self._default_watchlist))
        signals: list[BreakoutSignal] = []
        for _index, symbol in enumerate(symbols):
            filters = self._extract_filters(context)
            if not self._session_allowed(context.clock.now, filters):
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
                trend = context.features.lookup(
                    symbol=symbol, feature="regime_trend_1h", timeframe="1h"
                )
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

            entry_params = context.parameters.get("entry") if isinstance(context.parameters, Mapping) else {}
            buffer_params = entry_params.get("buffer") if isinstance(entry_params, Mapping) else {}
            buffer_min = self._coerce_float(
                buffer_params.get("min_abs") if isinstance(buffer_params, Mapping) else None
            )
            buffer_mult = self._coerce_float(
                buffer_params.get("atr_multiplier") if isinstance(buffer_params, Mapping) else None
            )
            buffer_min = buffer_min if buffer_min is not None else 0.05
            buffer_mult = buffer_mult if buffer_mult is not None else 0.02
            buffer = max(buffer_min, atr_v * buffer_mult)
            breakout: str | None = None
            level = None
            direction = None
            rationale = ""
            if close_v > upper_v + buffer:
                breakout = "upper"
                level = upper_v
                rationale = "breakout_upper"
            elif close_v < lower_v - buffer:
                breakout = "lower"
                level = lower_v
                rationale = "breakout_lower"
            elif mid_v is not None and abs(close_v - mid_v) <= atr_v * 0.1:
                # avoid mid-chop
                continue
            else:
                continue

            direction = self._resolve_direction(breakout)
            if direction is None:
                continue

            execution = self._extract_execution(context)
            filter_flags: dict[str, bool] = {}
            filter_block_reason = None
            breakout_width = abs(close_v - (level or close_v))

            trend_required = bool(filters.get("trend_required"))
            trend_threshold = self._coerce_float(filters.get("trend_threshold")) or 0.0
            trend_value = self._latest(trend)
            if trend_required:
                if trend_value is None:
                    filter_flags["trend_ok"] = False
                    filter_block_reason = "trend_missing"
                elif direction == "long":
                    filter_flags["trend_ok"] = trend_value > trend_threshold
                    filter_block_reason = None if filter_flags["trend_ok"] else "trend_mismatch"
                else:
                    filter_flags["trend_ok"] = trend_value < -trend_threshold
                    filter_block_reason = None if filter_flags["trend_ok"] else "trend_mismatch"

            atr_min = self._coerce_float(filters.get("atr_min"))
            if atr_min is not None:
                filter_flags["atr_ok"] = atr_v >= atr_min
                if not filter_flags["atr_ok"]:
                    filter_block_reason = filter_block_reason or "atr_below_min"

            min_breakout_abs = self._coerce_float(filters.get("min_breakout_abs"))
            breakout_min_atr_mult = self._coerce_float(filters.get("breakout_min_atr_mult"))
            breakout_min_cost_mult = self._coerce_float(filters.get("breakout_min_cost_mult"))

            thresholds: list[float] = []
            if min_breakout_abs is not None:
                thresholds.append(min_breakout_abs)
            if breakout_min_atr_mult is not None:
                thresholds.append(breakout_min_atr_mult * atr_v)
            if breakout_min_cost_mult is not None:
                spread = self._coerce_float(execution.get("spread")) or 0.0
                slippage = self._coerce_float(execution.get("slippage")) or 0.0
                cost = spread + slippage
                if cost > 0:
                    thresholds.append(breakout_min_cost_mult * cost)

            breakout_threshold = max(thresholds) if thresholds else None
            quality_score = None
            if breakout_threshold is not None:
                filter_flags["breakout_quality_ok"] = breakout_width >= breakout_threshold
                if breakout_threshold > 0:
                    quality_score = breakout_width / breakout_threshold
                if not filter_flags["breakout_quality_ok"]:
                    filter_block_reason = filter_block_reason or "breakout_quality"

            min_quality_score = self._coerce_float(filters.get("min_quality_score"))
            if min_quality_score is not None:
                filter_flags["quality_score_ok"] = (
                    quality_score is not None and quality_score >= min_quality_score
                )
                if not filter_flags["quality_score_ok"]:
                    filter_block_reason = filter_block_reason or "quality_score_below_min"

            if filter_block_reason is not None:
                continue

            signals.append(
                BreakoutSignal(
                    strategy_id=self.id,
                    symbol=symbol,
                    direction=direction or "long",
                    breakout=breakout,
                    level=level,
                    buffer=buffer,
                    rationale=rationale,
                    breakout_width=breakout_width,
                    filter_flags=filter_flags or None,
                    filter_block_reason=None,
                    quality_score=quality_score,
                )
            )
        return signals

    def required_warmup_bars(self) -> int:
        return 120

    def cooldown_bars(self) -> int:
        return 3

    def evaluate(self, context: StrategyContext) -> Iterable[BreakoutSignal]:
        return self.generate_signals(context)

class DonchianBreakoutStrategy(_BaseDonchianBreakoutStrategy):
    """Bidirectional Donchian breakout (upper=long / lower=short)."""

    id = "m1_baseline_donchian"
    determinism_key = "donchian_v1"
    mode = "bidirectional"
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


class DonchianBreakoutLongOnlyStrategy(_BaseDonchianBreakoutStrategy):
    """Donchian breakout with long-only execution (upper/lower both long)."""

    id = "m1_baseline_donchian_long_only"
    determinism_key = "donchian_v1_long_only"
    mode = "long_only"
    metadata = StrategyMetadata(
        name="M1 Baseline Donchian (Long Only)",
        version="0.1.0",
        required_features=DonchianBreakoutStrategy.metadata.required_features,
        tags=frozenset({"baseline", "breakout", "long_only"}),
    )


class DonchianBreakoutUpperOnlyStrategy(_BaseDonchianBreakoutStrategy):
    """Donchian breakout with upper-band long only (lower ignored)."""

    id = "m1_baseline_donchian_upper_only"
    determinism_key = "donchian_v1_upper_only"
    mode = "upper_only"
    metadata = StrategyMetadata(
        name="M1 Baseline Donchian (Upper Only)",
        version="0.1.0",
        required_features=DonchianBreakoutStrategy.metadata.required_features,
        tags=frozenset({"baseline", "breakout", "upper_only"}),
    )


__all__ = [
    "DonchianBreakoutStrategy",
    "DonchianBreakoutLongOnlyStrategy",
    "DonchianBreakoutUpperOnlyStrategy",
    "BreakoutSignal",
]
