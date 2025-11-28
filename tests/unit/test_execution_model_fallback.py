"""Execution model fallback behaviour for degraded stats."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import yaml

from src.execution.model import DeterministicExecutionModel


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

    normal = model.apply(signal, market_snapshot, spread_state=SimpleNamespace(state="normal"), mode_context=SimpleNamespace(mode="live", deterministic_seed=123))
    degraded = model.apply(signal, market_snapshot, spread_state=SimpleNamespace(state="normal"), mode_context=mode_context)

    assert degraded.ttl_seconds > normal.ttl_seconds
    assert degraded.expected_slippage is not None
    assert normal.expected_slippage is not None
    assert degraded.expected_slippage >= normal.expected_slippage
