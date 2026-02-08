from __future__ import annotations

from dataclasses import dataclass

from src.features.pipeline import FeatureLookupError
from src.strategies.base import StrategyContext
from src.strategies.donchian import (
    DonchianBreakoutLongOnlyStrategy,
    DonchianBreakoutStrategy,
    DonchianBreakoutUpperOnlyStrategy,
)


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


def test_donchian_strategy_skips_mid_check_when_missing() -> None:
    strategy = DonchianBreakoutStrategy(default_watchlist=("USDJPY",))
    required = strategy.metadata.required_features
    payloads = {
        "donchian_upper20_1h": 101.0,
        "donchian_lower20_1h": 99.0,
        "donchian_mid20_1h": None,
        "donchian_upper20_1d": None,
        "donchian_lower20_1d": None,
        "donchian_mid20_1d": None,
        "atr_14_1h": 0.5,
        "close_5m": 100.0,
        "regime_trend_1h": 1,
        "session_tag_5m": "london",
    }
    features = _FeatureStub(available_keys=required, payloads=payloads)
    context = StrategyContext(
        features=features,
        regime=object(),
        gate=object(),
        account=object(),
        config=object(),
        watchlist=frozenset({"USDJPY"}),
        clock=_ClockStub(now=type("T", (), {"hour": 12})()),
        seed=0,
    )

    signals = list(strategy.generate_signals(context))

    assert signals == []


def _context_for_close(
    close_value: float,
    *,
    trend_value: float = 1.0,
    parameters: dict | None = None,
    hour: int = 12,
) -> StrategyContext:
    strategy = DonchianBreakoutStrategy(default_watchlist=("USDJPY",))
    required = strategy.metadata.required_features
    payloads = {
        "donchian_upper20_1h": 101.0,
        "donchian_lower20_1h": 99.0,
        "donchian_mid20_1h": 100.0,
        "donchian_upper20_1d": None,
        "donchian_lower20_1d": None,
        "donchian_mid20_1d": None,
        "atr_14_1h": 1.0,
        "close_5m": close_value,
        "regime_trend_1h": trend_value,
        "session_tag_5m": "london",
    }
    features = _FeatureStub(available_keys=required, payloads=payloads)
    return StrategyContext(
        features=features,
        regime=object(),
        gate=object(),
        account=object(),
        config=object(),
        watchlist=frozenset({"USDJPY"}),
        clock=_ClockStub(now=type("T", (), {"hour": hour})()),
        seed=0,
        parameters=parameters or {},
    )


def test_donchian_long_only_emits_long_on_lower() -> None:
    strategy = DonchianBreakoutLongOnlyStrategy(default_watchlist=("USDJPY",))
    context = _context_for_close(98.0)

    signals = list(strategy.generate_signals(context))

    assert len(signals) == 1
    assert signals[0].direction == "long"
    assert signals[0].rationale == "breakout_lower"


def test_donchian_upper_only_ignores_lower() -> None:
    strategy = DonchianBreakoutUpperOnlyStrategy(default_watchlist=("USDJPY",))
    lower_context = _context_for_close(98.0)
    upper_context = _context_for_close(102.0)

    lower_signals = list(strategy.generate_signals(lower_context))
    upper_signals = list(strategy.generate_signals(upper_context))

    assert lower_signals == []
    assert len(upper_signals) == 1
    assert upper_signals[0].direction == "long"


def test_donchian_filters_block_on_trend() -> None:
    strategy = DonchianBreakoutStrategy(default_watchlist=("USDJPY",))
    params = {
        "entry": {
            "filters": {
                "trend_required": True,
                "trend_threshold": 0.0,
            }
        }
    }
    context = _context_for_close(102.0, trend_value=-1.0, parameters=params)

    signals = list(strategy.generate_signals(context))

    assert signals == []


def test_donchian_filters_block_on_breakout_quality() -> None:
    strategy = DonchianBreakoutStrategy(default_watchlist=("USDJPY",))
    params = {
        "entry": {
            "filters": {
                "min_breakout_abs": 5.0,
                "breakout_min_atr_mult": 0.3,
            }
        },
        "execution": {"spread": 0.005, "slippage": 0.0015},
    }
    context = _context_for_close(102.0, trend_value=1.0, parameters=params)

    signals = list(strategy.generate_signals(context))

    assert signals == []


def test_donchian_filters_from_root_parameters() -> None:
    strategy = DonchianBreakoutStrategy(default_watchlist=("USDJPY",))
    params = {
        "filters": {
            "trend_required": True,
            "trend_threshold": 0.0,
            "min_breakout_abs": 5.0,
        }
    }
    context = _context_for_close(102.0, trend_value=1.0, parameters=params)

    signals = list(strategy.generate_signals(context))

    assert signals == []


def test_donchian_session_filter_blocks_outside_range() -> None:
    strategy = DonchianBreakoutStrategy(default_watchlist=("USDJPY",))
    params = {"filters": {"session_utc_range": "06-14"}}
    context = _context_for_close(102.0, trend_value=1.0, parameters=params, hour=18)

    signals = list(strategy.generate_signals(context))

    assert signals == []
