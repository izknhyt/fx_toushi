"""Execution model fallback behaviour for degraded stats."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml
from src.execution.model import DeterministicExecutionModel, ExecutionRuleViolationError


def test_apply_uses_fallback_for_degraded_stats(project_root: Path) -> None:
    config_path = project_root / "config" / "execution_model.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    model = DeterministicExecutionModel(config)

    mode_context = SimpleNamespace(
        mode="live",
        deterministic_seed=123,
        latency_data_status="degraded",
        slippage_data_status="halt_recommended",
    )
    signal = SimpleNamespace(symbol="EURUSD", entry_mode=None, price=1.0942)
    market_snapshot = {"mid": 1.0942}

    normal = model.apply(
        signal,
        market_snapshot,
        spread_state=SimpleNamespace(state="normal"),
        mode_context=SimpleNamespace(mode="live", deterministic_seed=123),
    )
    degraded = model.apply(
        signal,
        market_snapshot,
        spread_state=SimpleNamespace(state="normal"),
        mode_context=mode_context,
    )

    assert degraded.ttl_seconds > normal.ttl_seconds
    assert degraded.expected_slippage is not None
    assert normal.expected_slippage is not None
    assert degraded.expected_slippage >= normal.expected_slippage


def test_apply_rejects_spread_above_threshold(project_root: Path) -> None:
    config_path = project_root / "config" / "execution_model.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    model = DeterministicExecutionModel(config)
    signal = SimpleNamespace(symbol="EURUSD", entry_mode="market", price=1.0, spread_pips=5.0)
    market_snapshot = {"mid": 1.0, "spread_pips": 5.0}

    try:
        model.apply(
            signal,
            market_snapshot,
            spread_state=SimpleNamespace(state="normal"),
            mode_context=SimpleNamespace(mode="live", deterministic_seed=1),
        )
    except ExecutionRuleViolationError:
        return
    raise AssertionError("Expected ExecutionRuleViolationError for high spread")


def test_apply_uses_observed_slippage_and_rollover(project_root: Path) -> None:
    config_path = project_root / "config" / "execution_model.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    model = DeterministicExecutionModel(config)
    signal = SimpleNamespace(symbol="USDJPY", entry_mode="market", price=150.0, spread_pips=0.2)
    market_snapshot = {
        "mid": 150.0,
        "spread_pips": 0.2,
        "observed_slippage_pips": 1.5,
        "rollover_pips": 0.3,
    }
    mode_ctx = SimpleNamespace(mode="paper", deterministic_seed=7, slippage_samples=[1.2, 1.4])

    adjustments = model.apply(
        signal, market_snapshot, spread_state=SimpleNamespace(state="normal"), mode_context=mode_ctx
    )

    assert adjustments.expected_slippage is not None
    assert adjustments.expected_slippage >= 1.5


def test_apply_prefers_slippage_log_when_available(project_root: Path) -> None:
    config_path = project_root / "config" / "execution_model.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    model = DeterministicExecutionModel(config)
    signal = SimpleNamespace(symbol="EURUSD", entry_mode="market", price=1.1, spread_pips=0.2)
    market_snapshot = {
        "mid": 1.1,
        "spread_pips": 0.2,
        "slippage_log": {"avg_pips": 2.4, "p95": 3.0},
        "spread_observations": [0.3, 0.5],
    }
    mode_ctx = SimpleNamespace(mode="live", deterministic_seed=4)

    adjustments = model.apply(
        signal, market_snapshot, spread_state=SimpleNamespace(state="normal"), mode_context=mode_ctx
    )

    assert adjustments.expected_slippage is not None
    assert adjustments.expected_slippage >= 2.4


def test_apply_uses_rollover_log_when_present(project_root: Path) -> None:
    config_path = project_root / "config" / "execution_model.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    model = DeterministicExecutionModel(config)
    signal = SimpleNamespace(symbol="EURUSD", entry_mode="market", price=1.1, spread_pips=0.1)
    market_snapshot = {
        "mid": 1.1,
        "spread_pips": 0.1,
        "rollover_log": {"last_pips": 2.8, "avg_pips": 1.9},
    }
    mode_ctx = SimpleNamespace(mode="paper", deterministic_seed=2)

    adjustments = model.apply(
        signal, market_snapshot, spread_state=SimpleNamespace(state="normal"), mode_context=mode_ctx
    )

    assert adjustments.expected_slippage is not None
    assert adjustments.expected_slippage >= 2.8
