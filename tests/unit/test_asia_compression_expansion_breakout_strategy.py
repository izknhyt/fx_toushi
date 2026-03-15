from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace

from src.features.pipeline import FeatureLookupError
from src.strategies.asia_compression_expansion_breakout import (
    AsiaCompressionExpansionBreakoutStrategy,
)
from src.strategies.base import StrategyContext


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


def _context(
    *,
    now: datetime,
    payloads: dict[str, object],
    params: dict | None = None,
    gate: object | None = None,
    config: object | None = None,
) -> StrategyContext:
    strategy = AsiaCompressionExpansionBreakoutStrategy(default_watchlist=("USDJPY",))
    features = _FeatureStub(
        available_keys=strategy.metadata.required_features,
        payloads=payloads,
    )
    default_gate = SimpleNamespace(
        risk=SimpleNamespace(kill_switch_recommendation=None, reduce_only=False),
        market=SimpleNamespace(profit_readiness_status="ok"),
        human=SimpleNamespace(),
        schema_version="test",
    )
    return StrategyContext(
        features=features,
        regime=object(),
        gate=gate or default_gate,
        account=object(),
        config=config or SimpleNamespace(board_mode="normal"),
        watchlist=frozenset({"USDJPY"}),
        clock=SimpleNamespace(now=now, timeframe="5m"),
        seed=7,
        parameters=params or {},
    )


def _bar_payload(
    *,
    open_v: float,
    high_v: float,
    low_v: float,
    close_v: float,
    volume_v: float,
    atr_v: float = 0.2,
    trend_v: float = 0.0,
    session_tag: str = "asia",
) -> dict[str, object]:
    return {
        "open_5m": open_v,
        "high_5m": high_v,
        "low_5m": low_v,
        "close_5m": close_v,
        "volume_5m": volume_v,
        "atr_14_1h": atr_v,
        "session_tag_5m": session_tag,
        "regime_trend_1h": trend_v,
    }


def _strategy_params() -> dict:
    return {
        "entry": {
            "session_utc_range": "00-12",
            "compression_start_utc": "00:00",
            "compression_minutes": 30,
            "breakout_session_utc_range": "00-12",
            "max_signals_per_session": 1,
            "allowed_session_tags": ["asia", "tokyo", "overlap", "london"],
            "filters": {
                "min_compression_abs": 0.12,
                "compression_atr_mult": 0.9,
                "min_breakout_abs": 0.03,
                "breakout_atr_mult": 0.25,
                "breakout_cost_mult": 2.5,
                "expansion_min_abs": 0.03,
                "expansion_atr_mult": 0.10,
            },
        },
        "execution": {"spread": 0.005, "slippage": 0.0015},
    }


def _prime_compression(
    strategy: AsiaCompressionExpansionBreakoutStrategy,
    params: dict,
) -> None:
    bars = [
        (
            datetime(2025, 1, 2, 0, 0, tzinfo=timezone.utc),
            _bar_payload(
                open_v=150.00, high_v=150.05, low_v=149.96, close_v=150.01, volume_v=100
            ),
        ),
        (
            datetime(2025, 1, 2, 0, 5, tzinfo=timezone.utc),
            _bar_payload(
                open_v=150.01, high_v=150.07, low_v=149.98, close_v=150.00, volume_v=100
            ),
        ),
        (
            datetime(2025, 1, 2, 0, 10, tzinfo=timezone.utc),
            _bar_payload(
                open_v=150.00, high_v=150.08, low_v=149.98, close_v=150.03, volume_v=100
            ),
        ),
        (
            datetime(2025, 1, 2, 0, 15, tzinfo=timezone.utc),
            _bar_payload(
                open_v=150.03, high_v=150.06, low_v=149.97, close_v=150.01, volume_v=100
            ),
        ),
        (
            datetime(2025, 1, 2, 0, 20, tzinfo=timezone.utc),
            _bar_payload(
                open_v=150.01, high_v=150.04, low_v=149.96, close_v=150.00, volume_v=100
            ),
        ),
        (
            datetime(2025, 1, 2, 0, 25, tzinfo=timezone.utc),
            _bar_payload(
                open_v=150.00, high_v=150.06, low_v=149.98, close_v=150.02, volume_v=100
            ),
        ),
    ]
    for ts, payload in bars:
        signals = list(strategy.generate_signals(_context(now=ts, payloads=payload, params=params)))
        assert signals == []


def test_compression_range_is_built_without_lookahead() -> None:
    strategy = AsiaCompressionExpansionBreakoutStrategy(default_watchlist=("USDJPY",))
    params = _strategy_params()
    _prime_compression(strategy, params)

    state = strategy._state_by_symbol["USDJPY"]
    assert state.compression_high == 150.08
    assert state.compression_low == 149.96
    assert state.compression_bars == 6


def test_breakout_after_compression_emits_signal() -> None:
    strategy = AsiaCompressionExpansionBreakoutStrategy(default_watchlist=("USDJPY",))
    params = _strategy_params()
    _prime_compression(strategy, params)

    breakout_bar = _context(
        now=datetime(2025, 1, 2, 0, 30, tzinfo=timezone.utc),
        payloads=_bar_payload(
            open_v=150.04,
            high_v=150.30,
            low_v=150.03,
            close_v=150.28,
            volume_v=110,
        ),
        params=params,
    )
    signals = list(strategy.generate_signals(breakout_bar))
    assert len(signals) == 1
    assert signals[0].direction == "long"
    assert signals[0].rationale == "asia_compression_expansion_breakout"
    assert signals[0].compression_range is not None
    assert signals[0].cost_estimate is not None


def test_hard_filters_block_kill_switch_board_mode_and_spread() -> None:
    params = _strategy_params()
    params["entry"]["filters"]["spread_max"] = 0.005  # type: ignore[index]
    params["execution"] = {"spread": 0.01, "slippage": 0.0015}

    def _breakout_context(*, gate: object | None = None, config: object | None = None) -> StrategyContext:
        return _context(
            now=datetime(2025, 1, 2, 0, 30, tzinfo=timezone.utc),
            payloads=_bar_payload(
                open_v=150.04,
                high_v=150.30,
                low_v=150.03,
                close_v=150.28,
                volume_v=110,
            ),
            params=params,
            gate=gate,
            config=config,
        )

    strategy_kill = AsiaCompressionExpansionBreakoutStrategy(default_watchlist=("USDJPY",))
    _prime_compression(strategy_kill, params)
    kill_gate = SimpleNamespace(
        risk=SimpleNamespace(kill_switch_recommendation="soft_stop", reduce_only=False),
        market=SimpleNamespace(profit_readiness_status="ok"),
        human=SimpleNamespace(),
        schema_version="test",
    )
    assert list(strategy_kill.generate_signals(_breakout_context(gate=kill_gate))) == []

    strategy_board = AsiaCompressionExpansionBreakoutStrategy(default_watchlist=("USDJPY",))
    _prime_compression(strategy_board, params)
    halted_config = SimpleNamespace(board_mode="halted")
    assert list(strategy_board.generate_signals(_breakout_context(config=halted_config))) == []

    strategy_spread = AsiaCompressionExpansionBreakoutStrategy(default_watchlist=("USDJPY",))
    _prime_compression(strategy_spread, params)
    assert list(strategy_spread.generate_signals(_breakout_context())) == []


def test_time_filter_blocks_outside_breakout_window() -> None:
    strategy = AsiaCompressionExpansionBreakoutStrategy(default_watchlist=("USDJPY",))
    params = _strategy_params()
    params["entry"]["breakout_session_utc_range"] = "06-12"  # type: ignore[index]
    _prime_compression(strategy, params)

    breakout_bar = _context(
        now=datetime(2025, 1, 2, 0, 30, tzinfo=timezone.utc),
        payloads=_bar_payload(
            open_v=150.04,
            high_v=150.30,
            low_v=150.03,
            close_v=150.28,
            volume_v=110,
        ),
        params=params,
    )
    assert list(strategy.generate_signals(breakout_bar)) == []


def test_cost_threshold_blocks_when_compression_too_narrow_for_cost() -> None:
    strategy = AsiaCompressionExpansionBreakoutStrategy(default_watchlist=("USDJPY",))
    params = _strategy_params()
    params["execution"] = {"spread": 0.02, "slippage": 0.01}
    params["entry"]["filters"]["max_cost_to_range_ratio"] = 0.20  # type: ignore[index]
    _prime_compression(strategy, params)

    breakout_bar = _context(
        now=datetime(2025, 1, 2, 0, 30, tzinfo=timezone.utc),
        payloads=_bar_payload(
            open_v=150.04,
            high_v=150.30,
            low_v=150.03,
            close_v=150.28,
            volume_v=110,
        ),
        params=params,
    )
    assert list(strategy.generate_signals(breakout_bar)) == []


def test_atr_floor_blocks_low_atr_breakout() -> None:
    strategy = AsiaCompressionExpansionBreakoutStrategy(default_watchlist=("USDJPY",))
    params = _strategy_params()
    params["entry"]["filters"]["atr_min"] = 0.25  # type: ignore[index]
    _prime_compression(strategy, params)

    breakout_bar = _context(
        now=datetime(2025, 1, 2, 0, 30, tzinfo=timezone.utc),
        payloads=_bar_payload(
            open_v=150.04,
            high_v=150.30,
            low_v=150.03,
            close_v=150.28,
            volume_v=110,
            atr_v=0.20,
        ),
        params=params,
    )
    assert list(strategy.generate_signals(breakout_bar)) == []


def test_allowed_directions_blocks_short_breakout_when_long_only() -> None:
    strategy = AsiaCompressionExpansionBreakoutStrategy(default_watchlist=("USDJPY",))
    params = _strategy_params()
    params["entry"]["allowed_directions"] = ["long"]  # type: ignore[index]
    _prime_compression(strategy, params)

    short_breakout = _context(
        now=datetime(2025, 1, 2, 0, 30, tzinfo=timezone.utc),
        payloads=_bar_payload(
            open_v=149.99,
            high_v=149.98,
            low_v=149.70,
            close_v=149.72,
            volume_v=110,
        ),
        params=params,
    )
    assert list(strategy.generate_signals(short_breakout)) == []
