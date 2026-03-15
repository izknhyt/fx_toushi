from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from src.strategies.allocation import StrategyAllocationPolicy
from src.strategies.base import StrategyContext, StrategyMetadata, StrategyPluginProtocol
from src.strategies.registry import StrategyEngine


@dataclass(frozen=True, slots=True)
class _Signal:
    strategy_id: str
    symbol: str
    direction: str
    score: float
    confidence: float


@dataclass(slots=True)
class _FeatureStub:
    available_keys: frozenset[str]
    symbols: frozenset[str]

    def lookup(self, *, symbol: str, feature: str, timeframe: str):  # noqa: ANN001
        if feature == "regime_trend_1h":
            return 0.2
        if feature == "close_5m":
            return 150.0
        raise KeyError(feature)

    def get_latest(self, *, symbol: str, feature: str, timeframe: str):  # noqa: ANN001
        return self.lookup(symbol=symbol, feature=feature, timeframe=timeframe)


class _AlphaStrategy(StrategyPluginProtocol):
    id = "alpha"
    determinism_key = "alpha_v1"
    metadata = StrategyMetadata(
        name="Alpha",
        version="0.1.0",
        required_features=frozenset({"close_5m"}),
    )

    def __init__(self) -> None:
        self.context: StrategyContext | None = None

    def required_warmup_bars(self) -> int:
        return 0

    def cooldown_bars(self) -> int:
        return 0

    def generate_signals(self, context: StrategyContext):
        self.context = context
        return [
            _Signal(
                strategy_id=self.id,
                symbol="USDJPY",
                direction="long",
                score=1.1,
                confidence=1.1,
            )
        ]

    def evaluate(self, context: StrategyContext):
        return self.generate_signals(context)


class _BetaStrategy(StrategyPluginProtocol):
    id = "beta"
    determinism_key = "beta_v1"
    metadata = StrategyMetadata(
        name="Beta",
        version="0.1.0",
        required_features=frozenset({"close_5m"}),
    )

    def __init__(self) -> None:
        self.context: StrategyContext | None = None

    def required_warmup_bars(self) -> int:
        return 0

    def cooldown_bars(self) -> int:
        return 0

    def generate_signals(self, context: StrategyContext):
        self.context = context
        return [
            _Signal(
                strategy_id=self.id,
                symbol="USDJPY",
                direction="long",
                score=1.0,
                confidence=1.0,
            )
        ]

    def evaluate(self, context: StrategyContext):
        return self.generate_signals(context)


def _write_manifest(path: Path) -> None:
    payload = {
        "schema_version": 0,
        "manifest_name": "allocation-test",
        "revision_tag": "test",
        "last_reviewed_at": "2026-01-01T00:00:00Z",
        "strategies": {
            "alpha": {
                "enabled": True,
                "priority": 10,
                "weight": 0.5,
                "determinism_key": "alpha_v1",
                "metadata": {
                    "name": "Alpha",
                    "version": "0.1.0",
                    "required_features": ["close_5m"],
                },
                "parameters": {"execution": {"spread": 0.001, "slippage": 0.001}},
            },
            "beta": {
                "enabled": True,
                "priority": 20,
                "weight": 0.5,
                "determinism_key": "beta_v1",
                "metadata": {
                    "name": "Beta",
                    "version": "0.1.0",
                    "required_features": ["close_5m"],
                },
                "parameters": {"execution": {"spread": 0.001, "slippage": 0.001}},
            },
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_policy(path: Path, *, selection_mode: str = "select_one") -> None:
    payload = {
        "profiles": {
            "active": {
                "mode": "active",
                "global": {
                    "require_strategy_config": True,
                    "selection": {"mode": selection_mode},
                    "hard_filters": {"session_utc_range": "00-23"},
                    "score": {"min_score": 0.0},
                },
                "tie_break": ["score_desc", "priority_asc", "strategy_id_asc"],
                "strategies": {
                    "alpha": {"enabled": True, "weight": 1.0},
                    "beta": {"enabled": True, "weight": 1.0},
                },
            }
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _run(engine: StrategyEngine, *, account: SimpleNamespace | None = None) -> list:
    features = _FeatureStub(
        available_keys=frozenset({"close_5m", "regime_trend_1h"}),
        symbols=frozenset({"USDJPY"}),
    )
    gate = SimpleNamespace(
        market=SimpleNamespace(profit_readiness_status="ok"),
        risk=SimpleNamespace(reduce_only=False, kill_switch_recommendation=None),
    )
    clock = SimpleNamespace(now=datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc), timeframe="5m")
    return engine.run_all(
        features=features,
        regime=SimpleNamespace(mode="normal"),
        gate=gate,
        account=account or SimpleNamespace(equity=1_000_000.0),
        config=SimpleNamespace(cfg_hash="test"),
        clock=clock,
        watchlist=["USDJPY"],
        seed=7,
    )


def test_strategy_engine_allocation_selects_one_candidate(tmp_path: Path) -> None:
    manifest_path = tmp_path / "strategy_manifest.yaml"
    policy_path = tmp_path / "strategy_allocation.yaml"
    _write_manifest(manifest_path)
    _write_policy(policy_path)

    engine = StrategyEngine()
    engine.register_plugin(_AlphaStrategy())
    engine.register_plugin(_BetaStrategy())
    engine.load_manifest(manifest_path)
    engine.set_allocation_policy(StrategyAllocationPolicy.load(policy_path, profile="active"))

    signals = _run(engine)

    assert len(signals) == 1
    assert signals[0].strategy_id == "alpha"


def test_strategy_engine_without_allocation_keeps_all_candidates(tmp_path: Path) -> None:
    manifest_path = tmp_path / "strategy_manifest.yaml"
    _write_manifest(manifest_path)

    engine = StrategyEngine()
    engine.register_plugin(_AlphaStrategy())
    engine.register_plugin(_BetaStrategy())
    engine.load_manifest(manifest_path)

    signals = _run(engine)

    assert len(signals) == 2
    assert {signal.strategy_id for signal in signals} == {"alpha", "beta"}


def test_strategy_engine_allocation_select_many_keeps_multiple_candidates(tmp_path: Path) -> None:
    manifest_path = tmp_path / "strategy_manifest.yaml"
    policy_path = tmp_path / "strategy_allocation.yaml"
    _write_manifest(manifest_path)
    _write_policy(policy_path, selection_mode="select_many")

    engine = StrategyEngine()
    engine.register_plugin(_AlphaStrategy())
    engine.register_plugin(_BetaStrategy())
    engine.load_manifest(manifest_path)
    engine.set_allocation_policy(StrategyAllocationPolicy.load(policy_path, profile="active"))

    signals = _run(engine)

    assert len(signals) == 2
    assert {signal.strategy_id for signal in signals} == {"alpha", "beta"}


def test_strategy_engine_allocation_respects_open_positions_from_account(tmp_path: Path) -> None:
    manifest_path = tmp_path / "strategy_manifest.yaml"
    policy_path = tmp_path / "strategy_allocation.yaml"
    _write_manifest(manifest_path)
    payload = {
        "profiles": {
            "active": {
                "mode": "active",
                "global": {
                    "require_strategy_config": True,
                    "selection": {"mode": "select_one"},
                    "hard_filters": {"session_utc_range": "00-23"},
                    "score": {"min_score": 0.0},
                },
                "tie_break": ["score_desc", "role_priority_asc", "priority_asc", "strategy_id_asc"],
                "strategies": {
                    "alpha_live": {
                        "enabled": True,
                        "weight": 1.0,
                        "portfolio": {"group": "trend_breakout"},
                    },
                    "alpha": {
                        "enabled": True,
                        "weight": 1.0,
                        "portfolio": {
                            "group": "trend_breakout",
                            "active_group_policy": "block",
                            "role_priority": 10,
                        },
                    },
                    "beta": {
                        "enabled": True,
                        "weight": 1.0,
                        "portfolio": {
                            "group": "us_pullback",
                            "role_priority": 20,
                        },
                    },
                },
            }
        }
    }
    policy_path.write_text(
        "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    engine = StrategyEngine()
    engine.register_plugin(_AlphaStrategy())
    engine.register_plugin(_BetaStrategy())
    engine.load_manifest(manifest_path)
    engine.set_allocation_policy(StrategyAllocationPolicy.load(policy_path, profile="active"))

    signals = _run(
        engine,
        account=SimpleNamespace(
            equity=1_000_000.0,
            positions=[
                {
                    "strategy_id": "alpha_live",
                    "symbol": "USDJPY",
                    "direction": "long",
                    "opened_at": datetime(2026, 1, 1, 17, 30, tzinfo=timezone.utc),
                }
            ],
        ),
    )

    assert len(signals) == 1
    assert signals[0].strategy_id == "beta"
