"""Asia-session compression -> expansion breakout strategy."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from src.strategies.base import StrategyContext, StrategyMetadata, StrategyPluginProtocol


@dataclass(frozen=True, slots=True)
class AsiaCompressionExpansionSignal:
    strategy_id: str
    symbol: str
    direction: str
    confidence: float
    rationale: str
    score: float
    quality_score: float
    compression_high: float | None = None
    compression_low: float | None = None
    compression_range: float | None = None
    breakout_distance: float | None = None
    atr_value: float | None = None
    cost_estimate: float | None = None


@dataclass(slots=True)
class _SessionState:
    session_date: date
    session_start: datetime
    compression_end: datetime
    compression_bars: int = 0
    compression_high: float | None = None
    compression_low: float | None = None
    compression_range: float | None = None
    compression_valid: bool = True
    signals_emitted: int = 0


class AsiaCompressionExpansionBreakoutStrategy(StrategyPluginProtocol):
    """Detect Asia compression and enter on London-side expansion breakout."""

    id = "m1_asia_compression_expansion_breakout"
    determinism_key = "asia_compression_expansion_breakout_v1"
    metadata = StrategyMetadata(
        name="M1 Asia Compression Expansion Breakout",
        version="0.1.0",
        required_features=frozenset(
            {
                "open_5m",
                "high_5m",
                "low_5m",
                "close_5m",
                "volume_5m",
                "atr_14_1h",
                "session_tag_5m",
                "regime_trend_1h",
            }
        ),
        tags=frozenset({"asia_session", "compression", "expansion", "breakout"}),
    )
    context: StrategyContext | None = None

    def __init__(self, *, default_watchlist: Sequence[str] | None = None) -> None:
        self._default_watchlist = tuple(default_watchlist or ("USDJPY",))
        self._state_by_symbol: dict[str, _SessionState] = {}

    @staticmethod
    def _extract_map(value: object) -> Mapping[str, object]:
        if isinstance(value, Mapping):
            return value
        return {}

    @staticmethod
    def _latest(value: object) -> object | None:
        if value is None:
            return None
        getter = getattr(value, "iloc", None)
        if getter is not None:
            try:
                return value.iloc[-1]
            except Exception:
                return None
        return value

    @staticmethod
    def _coerce_float(value: object, default: float = 0.0) -> float:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _coerce_int(value: object, default: int) -> int:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _as_datetime(value: object) -> datetime | None:
        if isinstance(value, datetime):
            return value
        to_pydatetime = getattr(value, "to_pydatetime", None)
        if callable(to_pydatetime):
            try:
                converted = to_pydatetime()
            except Exception:
                return None
            if isinstance(converted, datetime):
                return converted
        return None

    @staticmethod
    def _normalize_token(value: object, fallback: str = "") -> str:
        token = str(value).strip().lower() if value is not None else ""
        return token or fallback

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

    @staticmethod
    def _timeframe_to_minutes(token: str) -> int:
        normalized = token.strip().lower()
        if normalized.endswith("m"):
            return max(1, int(normalized[:-1]))
        if normalized.endswith("h"):
            return max(1, int(normalized[:-1])) * 60
        if normalized.endswith("d"):
            return max(1, int(normalized[:-1])) * 24 * 60
        return 5

    @staticmethod
    def _parse_hhmm(value: object, default_hour: int) -> tuple[int, int]:
        if isinstance(value, str):
            token = value.strip()
            if ":" in token:
                left, right = token.split(":", 1)
                try:
                    hour = int(left)
                    minute = int(right)
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        return hour, minute
                except ValueError:
                    pass
            else:
                try:
                    hour = int(token)
                    if 0 <= hour <= 23:
                        return hour, 0
                except ValueError:
                    pass
        return default_hour, 0

    @staticmethod
    def _parse_session_range(value: object, default_range: tuple[int, int]) -> tuple[int, int]:
        if not isinstance(value, str) or "-" not in value:
            return default_range
        left, right = value.split("-", 1)
        try:
            start = int(left.strip())
            end = int(right.strip())
        except ValueError:
            return default_range
        if not (0 <= start <= 23 and 0 <= end <= 23):
            return default_range
        return (start, end)

    @staticmethod
    def _session_allowed(*, ts: datetime, start: int, end: int) -> bool:
        if start <= end:
            return start <= ts.hour <= end
        return ts.hour >= start or ts.hour <= end

    @staticmethod
    def _allowed_token_set(value: object) -> frozenset[str]:
        if value is None:
            return frozenset()
        if isinstance(value, str):
            items = [part.strip() for part in value.split(",")]
        elif isinstance(value, (list, tuple, set, frozenset)):
            items = [str(item).strip() for item in value]
        else:
            items = [str(value).strip()]
        return frozenset(item.lower() for item in items if item)

    @staticmethod
    def _kill_switch_state(context: StrategyContext) -> str:
        risk = getattr(context.gate, "risk", None)
        explicit = getattr(risk, "kill_switch_recommendation", None)
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip().lower()
        if bool(getattr(risk, "reduce_only", False)):
            return "soft_stop"
        return "normal"

    @staticmethod
    def _board_mode(context: StrategyContext) -> str:
        direct = getattr(context.gate, "board_mode", None)
        if isinstance(direct, str) and direct.strip():
            return direct.strip().lower()
        config_mode = getattr(context.config, "board_mode", None)
        if isinstance(config_mode, str) and config_mode.strip():
            return config_mode.strip().lower()
        market = getattr(context.gate, "market", None)
        readiness = getattr(market, "profit_readiness_status", None)
        if isinstance(readiness, str):
            lowered = readiness.strip().lower()
            if lowered in {"guarded", "halted"}:
                return lowered
        return "normal"

    def _session_date(
        self,
        *,
        ts: datetime,
        start_hour: int,
        start_minute: int,
        wraps: bool,
    ) -> date:
        if not wraps:
            return ts.date()
        if (ts.hour, ts.minute) >= (start_hour, start_minute):
            return ts.date()
        return (ts - timedelta(days=1)).date()

    def _resolve_state(
        self,
        *,
        symbol: str,
        ts: datetime,
        session_start_hour: int,
        session_start_minute: int,
        session_wraps: bool,
        compression_minutes: int,
    ) -> _SessionState | None:
        session_date = self._session_date(
            ts=ts,
            start_hour=session_start_hour,
            start_minute=session_start_minute,
            wraps=session_wraps,
        )
        session_start = datetime.combine(
            session_date,
            time(session_start_hour, session_start_minute, tzinfo=timezone.utc),
        )
        if ts < session_start:
            return None
        compression_end = session_start + timedelta(minutes=compression_minutes)
        current = self._state_by_symbol.get(symbol)
        if current is None or current.session_date != session_date:
            current = _SessionState(
                session_date=session_date,
                session_start=session_start,
                compression_end=compression_end,
            )
            self._state_by_symbol[symbol] = current
            if len(self._state_by_symbol) > 64:
                stale = sorted(self._state_by_symbol.items(), key=lambda item: item[1].session_start)
                for stale_symbol, _state in stale[:-64]:
                    self._state_by_symbol.pop(stale_symbol, None)
        return current

    def generate_signals(self, context: StrategyContext) -> Iterable[AsiaCompressionExpansionSignal]:
        self.context = context
        if not self.metadata.required_features.issubset(context.features.available_keys):
            return []

        entry = self._entry_params(context)
        filters = self._filter_params(context)
        execution = self._execution_params(context)

        session_start, session_end = self._parse_session_range(
            entry.get("session_utc_range", filters.get("session_utc_range", "00-14")),
            default_range=(0, 14),
        )
        breakout_start, breakout_end = self._parse_session_range(
            entry.get("breakout_session_utc_range", filters.get("breakout_session_utc_range", "06-14")),
            default_range=(6, 14),
        )
        start_hour, start_minute = self._parse_hhmm(
            entry.get("compression_start_utc", "00:00"),
            default_hour=session_start,
        )
        session_wraps = session_start > session_end
        timeframe_minutes = self._timeframe_to_minutes(
            str(entry.get("timeframe", context.clock.timeframe or "5m"))
        )
        compression_minutes = max(timeframe_minutes, self._coerce_int(entry.get("compression_minutes"), 360))
        max_signals_per_session = max(
            1,
            self._coerce_int(entry.get("max_signals_per_session"), 1),
        )

        spread = max(0.0, self._coerce_float(execution.get("spread"), 0.0))
        slippage = max(0.0, self._coerce_float(execution.get("slippage"), 0.0))
        cost_estimate = spread + slippage

        spread_max = self._coerce_float(filters.get("spread_max"), -1.0)
        if spread_max >= 0 and spread > spread_max:
            return []

        blocked_kill_states = self._allowed_token_set(filters.get("kill_switch_blocked_states"))
        if not blocked_kill_states:
            blocked_kill_states = frozenset({"soft_stop", "hard_stop", "triggered"})
        if self._kill_switch_state(context) in blocked_kill_states:
            return []

        allowed_board_modes = self._allowed_token_set(filters.get("board_modes"))
        if not allowed_board_modes:
            allowed_board_modes = frozenset({"normal", "guarded"})
        if self._board_mode(context) not in allowed_board_modes:
            return []

        allowed_session_tags = self._allowed_token_set(
            entry.get("allowed_session_tags", filters.get("allowed_session_tags"))
        )
        allowed_directions = self._allowed_token_set(
            entry.get("allowed_directions", filters.get("allowed_directions"))
        )
        if not allowed_directions:
            allowed_directions = frozenset({"long", "short"})

        require_regime_alignment = bool(entry.get("require_regime_alignment", False))
        trend_min_abs = max(0.0, self._coerce_float(entry.get("trend_min_abs"), 0.0))

        min_volume = max(0.0, self._coerce_float(filters.get("min_volume"), 0.0))
        atr_min = max(0.0, self._coerce_float(filters.get("atr_min"), 0.0))
        min_compression_abs = max(0.0, self._coerce_float(filters.get("min_compression_abs"), 0.10))
        compression_atr_mult = max(0.0, self._coerce_float(filters.get("compression_atr_mult"), 0.90))
        min_breakout_abs = max(0.0, self._coerce_float(filters.get("min_breakout_abs"), 0.04))
        breakout_atr_mult = max(0.0, self._coerce_float(filters.get("breakout_atr_mult"), 0.30))
        breakout_cost_mult = max(0.0, self._coerce_float(filters.get("breakout_cost_mult"), 2.5))
        expansion_min_abs = max(0.0, self._coerce_float(filters.get("expansion_min_abs"), 0.03))
        expansion_atr_mult = max(0.0, self._coerce_float(filters.get("expansion_atr_mult"), 0.10))
        max_cost_to_range_ratio = self._coerce_float(filters.get("max_cost_to_range_ratio"), -1.0)

        now = self._as_datetime(context.clock.now)
        if now is None:
            return []
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)
        if not self._session_allowed(ts=now, start=session_start, end=session_end):
            return []

        symbols = sorted(context.watchlist or frozenset(self._default_watchlist))
        emitted: list[AsiaCompressionExpansionSignal] = []
        for symbol in symbols:
            state = self._resolve_state(
                symbol=symbol,
                ts=now,
                session_start_hour=start_hour,
                session_start_minute=start_minute,
                session_wraps=session_wraps,
                compression_minutes=compression_minutes,
            )
            if state is None or state.signals_emitted >= max_signals_per_session:
                continue

            try:
                open_value = self._coerce_float(
                    self._latest(
                        context.features.lookup(symbol=symbol, feature="open_5m", timeframe="5m")
                    ),
                    0.0,
                )
                high_value = self._coerce_float(
                    self._latest(
                        context.features.lookup(symbol=symbol, feature="high_5m", timeframe="5m")
                    ),
                    0.0,
                )
                low_value = self._coerce_float(
                    self._latest(
                        context.features.lookup(symbol=symbol, feature="low_5m", timeframe="5m")
                    ),
                    0.0,
                )
                close_value = self._coerce_float(
                    self._latest(
                        context.features.lookup(symbol=symbol, feature="close_5m", timeframe="5m")
                    ),
                    0.0,
                )
                volume_value = max(
                    0.0,
                    self._coerce_float(
                        self._latest(
                            context.features.lookup(
                                symbol=symbol, feature="volume_5m", timeframe="5m"
                            )
                        ),
                        0.0,
                    ),
                )
                atr_value = self._coerce_float(
                    self._latest(
                        context.features.lookup(symbol=symbol, feature="atr_14_1h", timeframe="1h")
                    ),
                    0.0,
                )
                session_tag_raw = self._latest(
                    context.features.lookup(symbol=symbol, feature="session_tag_5m", timeframe="5m")
                )
                trend_value = self._coerce_float(
                    self._latest(
                        context.features.lookup(
                            symbol=symbol, feature="regime_trend_1h", timeframe="1h"
                        )
                    ),
                    0.0,
                )
            except Exception:
                continue

            if high_value <= 0 or low_value <= 0 or close_value <= 0:
                continue
            if min_volume > 0 and volume_value < min_volume:
                continue
            if atr_value < atr_min:
                continue

            session_tag = self._normalize_token(session_tag_raw)
            if allowed_session_tags and session_tag not in allowed_session_tags:
                continue

            if now < state.compression_end:
                state.compression_bars += 1
                state.compression_high = (
                    high_value if state.compression_high is None else max(state.compression_high, high_value)
                )
                state.compression_low = (
                    low_value if state.compression_low is None else min(state.compression_low, low_value)
                )
                continue

            min_compression_bars = max(1, compression_minutes // timeframe_minutes)
            if (
                state.compression_bars < min_compression_bars
                or state.compression_high is None
                or state.compression_low is None
            ):
                continue

            if state.compression_range is None:
                compression_range = max(0.0, state.compression_high - state.compression_low)
                state.compression_range = compression_range
                if compression_range <= 0:
                    state.compression_valid = False
                max_allowed_range = max(min_compression_abs, atr_value * compression_atr_mult)
                if compression_range > max_allowed_range:
                    state.compression_valid = False

            if not state.compression_valid or state.compression_range is None:
                continue

            if max_cost_to_range_ratio >= 0 and state.compression_range > 0:
                if (cost_estimate / state.compression_range) > max_cost_to_range_ratio:
                    continue
            elif max_cost_to_range_ratio >= 0 and state.compression_range <= 0:
                continue

            if not self._session_allowed(ts=now, start=breakout_start, end=breakout_end):
                continue

            breakout_buffer = max(
                min_breakout_abs,
                atr_value * breakout_atr_mult,
                cost_estimate * breakout_cost_mult,
            )
            expansion_min = max(expansion_min_abs, atr_value * expansion_atr_mult)
            bar_range = max(0.0, high_value - low_value)

            long_breakout = (
                "long" in allowed_directions
                and close_value > (state.compression_high + breakout_buffer)
                and close_value >= open_value
                and bar_range >= expansion_min
            )
            short_breakout = (
                "short" in allowed_directions
                and close_value < (state.compression_low - breakout_buffer)
                and close_value <= open_value
                and bar_range >= expansion_min
            )
            if require_regime_alignment and trend_min_abs > 0:
                if long_breakout and trend_value < trend_min_abs:
                    long_breakout = False
                if short_breakout and trend_value > -trend_min_abs:
                    short_breakout = False

            if not long_breakout and not short_breakout:
                continue

            direction = "long" if long_breakout else "short"
            breakout_distance = (
                close_value - state.compression_high
                if direction == "long"
                else state.compression_low - close_value
            )
            quality = max(0.1, breakout_distance / max(cost_estimate, 1e-6))
            confidence = min(3.0, quality)

            emitted.append(
                AsiaCompressionExpansionSignal(
                    strategy_id=self.id,
                    symbol=symbol,
                    direction=direction,
                    confidence=round(confidence, 4),
                    rationale="asia_compression_expansion_breakout",
                    score=round(quality, 4),
                    quality_score=round(quality, 4),
                    compression_high=round(state.compression_high, 6),
                    compression_low=round(state.compression_low, 6),
                    compression_range=round(state.compression_range, 6),
                    breakout_distance=round(breakout_distance, 6),
                    atr_value=round(atr_value, 6),
                    cost_estimate=round(cost_estimate, 6),
                )
            )
            state.signals_emitted += 1
        return emitted

    def required_warmup_bars(self) -> int:
        return 120

    def cooldown_bars(self) -> int:
        return 1

    def evaluate(self, context: StrategyContext) -> Iterable[AsiaCompressionExpansionSignal]:
        return self.generate_signals(context)


__all__ = [
    "AsiaCompressionExpansionBreakoutStrategy",
    "AsiaCompressionExpansionSignal",
]
