"""Tests for KPI computation from returns."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from src.reporter.kpi import compute_kpi_from_equity, compute_kpi_from_returns


def test_compute_kpi_from_returns(tmp_path: Path) -> None:
    data = pd.DataFrame({"r": [0.02, -0.01, 0.03, 0.0]})
    path = tmp_path / "returns.csv"
    data.to_csv(path, index=False)

    kpi = compute_kpi_from_returns(path)

    assert kpi["win_rate"] == 0.5
    assert kpi["cum_r"] == 0.04
    assert kpi["max_dd"] >= 0.0
    assert kpi["sharpe"] != "n/a"


def test_compute_kpi_from_equity(tmp_path: Path) -> None:
    data = pd.DataFrame({"equity": [100, 102, 101, 104]})
    path = tmp_path / "equity.parquet"
    data.to_parquet(path)

    kpi = compute_kpi_from_equity(path)

    assert kpi["win_rate"] != "n/a"
    assert kpi["cum_r"] != "n/a"
