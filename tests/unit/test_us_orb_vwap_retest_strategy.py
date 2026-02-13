from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace

from src.features.pipeline import FeatureLookupError
from src.strategies.base import StrategyContext
from src.strategies.us_orb_vwap_retest import UsOpeningRangeBreakoutVwapRetestStrategy


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
    strategy = UsOpeningRangeBreakoutVwapRetestStrategy(default_watchlist=("USDJPY",))
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
    atr_v: float = 0.1,
    session_tag: str = "newyork",
) -> dict[str, object]:
    return {
        "open_5m": open_v,
        "high_5m": high_v,
        "low_5m": low_v,
        "close_5m": close_v,
        "volume_5m": volume_v,
        "atr_14_1h": atr_v,
        "session_tag_5m": session_tag,
    }


def test_orb_range_is_built_without_lookahead() -> None:
    strategy = UsOpeningRangeBreakoutVwapRetestStrategy(default_watchlist=("USDJPY",))
    bars = [
        (datetime(2025, 1, 2, 13, 30, tzinfo=timezone.utc), _bar_payload(open_v=150.00, high_v=150.10, low_v=149.90, close_v=150.00, volume_v=100)),
        (datetime(2025, 1, 2, 13, 35, tzinfo=timezone.utc), _bar_payload(open_v=150.00, high_v=150.20, low_v=149.95, close_v=150.15, volume_v=100)),
        (datetime(2025, 1, 2, 13, 40, tzinfo=timezone.utc), _bar_payload(open_v=150.15, high_v=150.25, low_v=150.00, close_v=150.10, volume_v=100)),
        (datetime(2025, 1, 2, 13, 45, tzinfo=timezone.utc), _bar_payload(open_v=150.10, high_v=150.22, low_v=149.98, close_v=150.05, volume_v=100)),
        (datetime(2025, 1, 2, 13, 50, tzinfo=timezone.utc), _bar_payload(open_v=150.05, high_v=150.18, low_v=149.97, close_v=150.02, volume_v=100)),
        (datetime(2025, 1, 2, 13, 55, tzinfo=timezone.utc), _bar_payload(open_v=150.02, high_v=150.24, low_v=149.96, close_v=150.20, volume_v=100)),
    ]

    for ts, payload in bars:
        signals = list(strategy.generate_signals(_context(now=ts, payloads=payload)))
        assert signals == []

    state = strategy._state_by_symbol["USDJPY"]
    assert state.orb_high == 150.25
    assert state.orb_low == 149.9
    assert state.orb_bars == 6


def test_breakout_then_vwap_retest_emits_signal() -> None:
    strategy = UsOpeningRangeBreakoutVwapRetestStrategy(default_watchlist=("USDJPY",))
    pre_bars = [
        (datetime(2025, 1, 2, 13, 30, tzinfo=timezone.utc), _bar_payload(open_v=150.00, high_v=150.10, low_v=149.90, close_v=150.00, volume_v=100)),
        (datetime(2025, 1, 2, 13, 35, tzinfo=timezone.utc), _bar_payload(open_v=150.00, high_v=150.20, low_v=149.95, close_v=150.15, volume_v=100)),
        (datetime(2025, 1, 2, 13, 40, tzinfo=timezone.utc), _bar_payload(open_v=150.15, high_v=150.25, low_v=150.00, close_v=150.10, volume_v=100)),
        (datetime(2025, 1, 2, 13, 45, tzinfo=timezone.utc), _bar_payload(open_v=150.10, high_v=150.22, low_v=149.98, close_v=150.05, volume_v=100)),
        (datetime(2025, 1, 2, 13, 50, tzinfo=timezone.utc), _bar_payload(open_v=150.05, high_v=150.18, low_v=149.97, close_v=150.02, volume_v=100)),
        (datetime(2025, 1, 2, 13, 55, tzinfo=timezone.utc), _bar_payload(open_v=150.02, high_v=150.24, low_v=149.96, close_v=150.20, volume_v=100)),
    ]
    for ts, payload in pre_bars:
        assert list(strategy.generate_signals(_context(now=ts, payloads=payload))) == []

    breakout_bar = _context(
        now=datetime(2025, 1, 2, 14, 0, tzinfo=timezone.utc),
        payloads=_bar_payload(
            open_v=150.20,
            high_v=150.40,
            low_v=150.30,
            close_v=150.35,
            volume_v=100,
        ),
    )
    assert list(strategy.generate_signals(breakout_bar)) == []
    assert strategy._state_by_symbol["USDJPY"].breakout_direction == "long"

    retest_bar = _context(
        now=datetime(2025, 1, 2, 14, 5, tzinfo=timezone.utc),
        payloads=_bar_payload(
            open_v=150.30,
            high_v=150.42,
            low_v=150.12,
            close_v=150.38,
            volume_v=100,
        ),
    )
    signals = list(strategy.generate_signals(retest_bar))
    assert len(signals) == 1
    assert signals[0].direction == "long"
    assert signals[0].rationale == "us_orb_breakout_vwap_retest_continue"
    assert signals[0].cost_estimate is not None


def test_hard_filters_block_kill_switch_board_mode_and_spread() -> None:
    strategy = UsOpeningRangeBreakoutVwapRetestStrategy(default_watchlist=("USDJPY",))
    ts = datetime(2025, 1, 2, 14, 5, tzinfo=timezone.utc)
    payload = _bar_payload(
        open_v=150.30,
        high_v=150.42,
        low_v=150.12,
        close_v=150.38,
        volume_v=100,
    )
    params = {
        "execution": {"spread": 0.01, "slippage": 0.0015},
        "entry": {
            "filters": {
                "spread_max": 0.005,
                "kill_switch_blocked_states": ["soft_stop", "hard_stop"],
                "board_modes": ["normal"],
            }
        },
    }

    kill_gate = SimpleNamespace(
        risk=SimpleNamespace(kill_switch_recommendation="soft_stop", reduce_only=False),
        market=SimpleNamespace(profit_readiness_status="ok"),
        human=SimpleNamespace(),
        schema_version="test",
    )
    assert list(strategy.generate_signals(_context(now=ts, payloads=payload, params=params, gate=kill_gate))) == []

    halted_config = SimpleNamespace(board_mode="halted")
    assert list(
        strategy.generate_signals(
            _context(now=ts, payloads=payload, params=params, config=halted_config)
        )
    ) == []

    normal_gate = SimpleNamespace(
        risk=SimpleNamespace(kill_switch_recommendation=None, reduce_only=False),
        market=SimpleNamespace(profit_readiness_status="ok"),
        human=SimpleNamespace(),
        schema_version="test",
    )
    assert list(
        strategy.generate_signals(
            _context(now=ts, payloads=payload, params=params, gate=normal_gate)
        )
    ) == []


def test_time_filter_blocks_outside_us_session() -> None:
    strategy = UsOpeningRangeBreakoutVwapRetestStrategy(default_watchlist=("USDJPY",))
    context = _context(
        now=datetime(2025, 1, 2, 10, 5, tzinfo=timezone.utc),
        payloads=_bar_payload(
            open_v=150.30,
            high_v=150.42,
            low_v=150.12,
            close_v=150.38,
            volume_v=100,
        ),
    )

    signals = list(strategy.generate_signals(context))
    assert signals == []


def test_cost_threshold_blocks_when_range_too_narrow_for_cost() -> None:
    strategy = UsOpeningRangeBreakoutVwapRetestStrategy(default_watchlist=("USDJPY",))
    params = {
        "execution": {"spread": 0.02, "slippage": 0.01},
        "entry": {
            "filters": {
                "max_cost_to_range_ratio": 0.05,
            }
        },
    }
    bars = [
        (datetime(2025, 1, 2, 13, 30, tzinfo=timezone.utc), _bar_payload(open_v=150.00, high_v=150.05, low_v=149.95, close_v=150.00, volume_v=100)),
        (datetime(2025, 1, 2, 13, 35, tzinfo=timezone.utc), _bar_payload(open_v=150.00, high_v=150.06, low_v=149.96, close_v=150.01, volume_v=100)),
        (datetime(2025, 1, 2, 13, 40, tzinfo=timezone.utc), _bar_payload(open_v=150.01, high_v=150.06, low_v=149.95, close_v=150.00, volume_v=100)),
        (datetime(2025, 1, 2, 13, 45, tzinfo=timezone.utc), _bar_payload(open_v=150.00, high_v=150.05, low_v=149.94, close_v=150.00, volume_v=100)),
        (datetime(2025, 1, 2, 13, 50, tzinfo=timezone.utc), _bar_payload(open_v=150.00, high_v=150.05, low_v=149.95, close_v=150.00, volume_v=100)),
        (datetime(2025, 1, 2, 13, 55, tzinfo=timezone.utc), _bar_payload(open_v=150.00, high_v=150.06, low_v=149.95, close_v=150.01, volume_v=100)),
        (datetime(2025, 1, 2, 14, 0, tzinfo=timezone.utc), _bar_payload(open_v=150.01, high_v=150.15, low_v=150.00, close_v=150.14, volume_v=100)),
        (datetime(2025, 1, 2, 14, 5, tzinfo=timezone.utc), _bar_payload(open_v=150.10, high_v=150.16, low_v=150.02, close_v=150.13, volume_v=100)),
    ]

    emitted = []
    for ts, payload in bars:
        emitted.extend(strategy.generate_signals(_context(now=ts, payloads=payload, params=params)))

    assert emitted == []


def test_allowed_directions_blocks_short_breakout_when_long_only() -> None:
    strategy = UsOpeningRangeBreakoutVwapRetestStrategy(default_watchlist=("USDJPY",))
    params = {
        "entry": {
            "allowed_directions": ["long"],
        }
    }

    pre_bars = [
        (datetime(2025, 1, 2, 13, 30, tzinfo=timezone.utc), _bar_payload(open_v=150.00, high_v=150.10, low_v=149.90, close_v=150.00, volume_v=100)),
        (datetime(2025, 1, 2, 13, 35, tzinfo=timezone.utc), _bar_payload(open_v=150.00, high_v=150.20, low_v=149.95, close_v=150.15, volume_v=100)),
        (datetime(2025, 1, 2, 13, 40, tzinfo=timezone.utc), _bar_payload(open_v=150.15, high_v=150.25, low_v=150.00, close_v=150.10, volume_v=100)),
        (datetime(2025, 1, 2, 13, 45, tzinfo=timezone.utc), _bar_payload(open_v=150.10, high_v=150.22, low_v=149.98, close_v=150.05, volume_v=100)),
        (datetime(2025, 1, 2, 13, 50, tzinfo=timezone.utc), _bar_payload(open_v=150.05, high_v=150.18, low_v=149.97, close_v=150.02, volume_v=100)),
        (datetime(2025, 1, 2, 13, 55, tzinfo=timezone.utc), _bar_payload(open_v=150.02, high_v=150.24, low_v=149.96, close_v=150.20, volume_v=100)),
    ]
    for ts, payload in pre_bars:
        assert list(strategy.generate_signals(_context(now=ts, payloads=payload, params=params))) == []

    short_breakout = _context(
        now=datetime(2025, 1, 2, 14, 0, tzinfo=timezone.utc),
        payloads=_bar_payload(
            open_v=149.95,
            high_v=149.90,
            low_v=149.60,
            close_v=149.65,
            volume_v=100,
        ),
        params=params,
    )
    assert list(strategy.generate_signals(short_breakout)) == []

    retest = _context(
        now=datetime(2025, 1, 2, 14, 5, tzinfo=timezone.utc),
        payloads=_bar_payload(
            open_v=149.70,
            high_v=149.90,
            low_v=149.62,
            close_v=149.66,
            volume_v=100,
        ),
        params=params,
    )
    assert list(strategy.generate_signals(retest)) == []
    assert strategy._state_by_symbol["USDJPY"].breakout_direction is None
