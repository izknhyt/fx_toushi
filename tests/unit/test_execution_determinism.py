from __future__ import annotations

import copy
from pathlib import Path

from src.execution.model import DeterministicExecutionModel
from tests.helpers.config import ConfigLoaderStub


def _model(config_path: str | Path) -> DeterministicExecutionModel:
    loader = ConfigLoaderStub()
    path = Path(config_path)
    cfg = loader(path)
    return DeterministicExecutionModel(cfg)


class _Signal:
    def __init__(self, *, entry_mode: str | None = None, price: float | None = None) -> None:
        self.entry_mode = entry_mode
        self.price = price
        self.symbol = "USDJPY"


def test_apply_human_delay_is_deterministic(project_root) -> None:
    model = _model(project_root / "config" / "execution_model.yaml")
    delay_a = model.apply_human_delay(seed=42)
    delay_b = model.apply_human_delay(seed=42)
    delay_c = model.apply_human_delay(seed=43)

    assert delay_a == delay_b
    assert delay_a != delay_c
    assert 0.0 <= delay_a <= 30.0


def test_execution_apply_uses_seed_in_mode_context(project_root) -> None:
    model = _model(project_root / "config" / "execution_model.yaml")
    signal = _Signal(entry_mode="marketable_limit", price=150.0)
    market = {"mid": 150.1}
    mode_ctx = {"mode": "paper", "deterministic_seed": 99, "latency_data_status": "ok", "slippage_data_status": "ok"}

    adjustments_a = model.apply(signal, market, spread_state={"state": "normal"}, mode_context=mode_ctx)
    adjustments_b = model.apply(signal, market, spread_state={"state": "normal"}, mode_context=copy.deepcopy(mode_ctx))

    assert adjustments_a.ttl_seconds == adjustments_b.ttl_seconds
    assert adjustments_a.expected_entry == 150.0 or adjustments_a.expected_entry == 150.1
