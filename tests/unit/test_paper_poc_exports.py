"""Tests for performance export from paper PoC result."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from src.backtest.paper_poc import PocResult, _export_series


def test_poc_result_can_export_returns_and_equity(tmp_path: Path) -> None:
    result = PocResult(
        metrics={},
        trades=[],
        dataset_path="dummy",
        dataset_hash="dummy",
        window={"from": "2025-01-01", "to": "2025-01-02"},
        returns=[0.01, -0.005, 0.02],
        equity_curve=[100, 101, 100.5, 102.5],
    )
    returns_path = tmp_path / "reports/performance/paper/returns.parquet"
    equity_path = tmp_path / "reports/performance/paper/equity.parquet"

    _export_series(returns_path, "r", pd.Series(result.returns))
    _export_series(equity_path, "equity", pd.Series(result.equity_curve))

    assert returns_path.with_suffix(".parquet").exists() or returns_path.with_suffix(".csv").exists() or returns_path.exists()
    assert equity_path.with_suffix(".parquet").exists() or equity_path.with_suffix(".csv").exists() or equity_path.exists()
