from __future__ import annotations

from dataclasses import dataclass

from src.features.pipeline import FeatureLookupError
from src.strategies.base import StrategyContext
from src.strategies.donchian import DonchianBreakoutStrategy


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
