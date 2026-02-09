from __future__ import annotations

from dataclasses import dataclass

from src.features.pipeline import FeatureLookupError
from src.strategies.base import StrategyContext
from src.strategies.us_session_momentum import UsSessionTrendPullbackStrategy


@dataclass
class _FeatureStub:
    available_keys: frozenset[str]
    payloads: dict[str, object]

    def lookup(self, *, symbol: str, feature: str, timeframe: str) -> object:
        if feature not in self.payloads:
            raise FeatureLookupError(symbol, timeframe, feature)
        return self.payloads[feature]

    def get_latest(self, *, symbol: str, feature: str, timeframe: str) -> object:
        return self.lookup(symbol=symbol, feature=feature, timeframe=timeframe)


@dataclass
class _ClockStub:
    now: object
    timeframe: str = "5m"


def _context(
    *,
    hour: int = 18,
    params: dict | None = None,
    overrides: dict[str, object] | None = None,
) -> StrategyContext:
    strategy = UsSessionTrendPullbackStrategy(default_watchlist=("USDJPY",))
    required = strategy.metadata.required_features
    payloads: dict[str, object] = {
        "ema_fast_5m": 151.0,
        "ema_slow_5m": 150.5,
        "rsi_14_5m": 55.0,
        "atr_14_1h": 0.2,
        "ema55_slope_1h": 0.08,
        "close_5m": 151.1,
        "session_tag_5m": "us",
        "regime_trend_1h": 0.3,
    }
    if overrides:
        payloads.update(overrides)
    return StrategyContext(
        features=_FeatureStub(available_keys=required, payloads=payloads),
        regime=object(),
        gate=object(),
        account=object(),
        config=object(),
        watchlist=frozenset({"USDJPY"}),
        clock=_ClockStub(now=type("T", (), {"hour": hour})()),
        seed=0,
        parameters=params or {},
    )


def test_us_session_strategy_generates_long_signal() -> None:
    strategy = UsSessionTrendPullbackStrategy(default_watchlist=("USDJPY",))
    context = _context()

    signals = list(strategy.generate_signals(context))

    assert len(signals) == 1
    assert signals[0].direction == "long"
    assert signals[0].score > 0


def test_us_session_strategy_blocks_outside_us_hours() -> None:
    strategy = UsSessionTrendPullbackStrategy(default_watchlist=("USDJPY",))
    context = _context(hour=10)

    signals = list(strategy.generate_signals(context))

    assert signals == []


def test_us_session_strategy_emits_short_on_downtrend_pullback() -> None:
    strategy = UsSessionTrendPullbackStrategy(default_watchlist=("USDJPY",))
    context = _context(
        overrides={
            "ema_fast_5m": 149.8,
            "ema_slow_5m": 150.4,
            "rsi_14_5m": 45.0,
            "ema55_slope_1h": -0.07,
            "close_5m": 149.7,
            "regime_trend_1h": -0.4,
        }
    )

    signals = list(strategy.generate_signals(context))

    assert len(signals) == 1
    assert signals[0].direction == "short"


def test_us_session_strategy_respects_atr_and_spread_filters() -> None:
    strategy = UsSessionTrendPullbackStrategy(default_watchlist=("USDJPY",))
    context = _context(
        params={
            "entry": {"filters": {"atr_min": 0.3, "spread_max": 0.003}},
            "execution": {"spread": 0.005},
        }
    )

    signals = list(strategy.generate_signals(context))

    assert signals == []


def test_us_session_strategy_blocks_configured_utc_hours() -> None:
    strategy = UsSessionTrendPullbackStrategy(default_watchlist=("USDJPY",))
    blocked_context = _context(
        hour=20,
        params={"entry": {"blocked_utc_hours": [20, 21]}},
    )
    allowed_context = _context(
        hour=22,
        params={"entry": {"blocked_utc_hours": [20, 21]}},
    )

    blocked_signals = list(strategy.generate_signals(blocked_context))
    allowed_signals = list(strategy.generate_signals(allowed_context))

    assert blocked_signals == []
    assert len(allowed_signals) == 1


def test_us_session_strategy_supports_overnight_session_ranges() -> None:
    strategy = UsSessionTrendPullbackStrategy(default_watchlist=("USDJPY",))
    allowed_context = _context(
        hour=23,
        params={"entry": {"session_utc_range": "22-02"}},
    )
    blocked_context = _context(
        hour=12,
        params={"entry": {"session_utc_range": "22-02"}},
    )

    allowed_signals = list(strategy.generate_signals(allowed_context))
    blocked_signals = list(strategy.generate_signals(blocked_context))

    assert len(allowed_signals) == 1
    assert blocked_signals == []


def test_us_session_strategy_parses_blocked_hours_from_string() -> None:
    strategy = UsSessionTrendPullbackStrategy(default_watchlist=("USDJPY",))
    blocked_context = _context(
        hour=21,
        params={"entry": {"blocked_utc_hours": "20, 21, x"}},
    )
    allowed_context = _context(
        hour=22,
        params={"entry": {"blocked_utc_hours": "20, 21, x"}},
    )

    blocked_signals = list(strategy.generate_signals(blocked_context))
    allowed_signals = list(strategy.generate_signals(allowed_context))

    assert blocked_signals == []
    assert len(allowed_signals) == 1
