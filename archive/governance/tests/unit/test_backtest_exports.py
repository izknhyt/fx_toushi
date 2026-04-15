"""Smoke tests for backtest performance exports and KPI parity."""

from __future__ import annotations

import json
from math import isclose
from pathlib import Path

import pandas as pd
from src.interfaces.cli.backtest import run_backtest
from src.reporter.kpi import compute_kpi_from_equity, compute_kpi_from_returns


def _resolve_existing(path: Path) -> Path:
    if path.exists():
        return path
    csv_candidate = path.with_suffix(".csv")
    if csv_candidate.exists():
        return csv_candidate
    return path


def test_run_backtest_exports_returns_and_equity(tmp_path: Path) -> None:
    data = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=6, freq="D"),
            "close": [100, 102, 101, 104, 106, 105],
        }
    )
    dataset_path = tmp_path / "dataset.parquet"
    data.to_parquet(dataset_path)
    manifest = {
        "strategies": {"demo": {"dataset_path": str(dataset_path), "dataset_sha256": "deadbeef"}}
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    returns_path = tmp_path / "perf" / "returns.parquet"
    equity_path = tmp_path / "perf" / "equity.parquet"
    payload = run_backtest(
        strategy="demo",
        profile="paper",
        window_from="2025-01-01",
        window_to="2025-01-06",
        export=None,
        output=None,
        out_dir=tmp_path / "out",
        manifest_path=manifest_path,
        returns_path=returns_path,
        equity_path=equity_path,
        base_equity=100.0,
    )

    returns_file = _resolve_existing(returns_path)
    equity_file = _resolve_existing(equity_path)

    assert returns_file.exists()
    assert equity_file.exists()
    assert payload.get("performance_exports")

    kpi_from_returns = compute_kpi_from_returns(returns_file)
    kpi_from_equity = compute_kpi_from_equity(equity_file)

    assert kpi_from_returns["win_rate"] != "n/a"
    assert kpi_from_equity["win_rate"] != "n/a"
    assert isclose(
        float(kpi_from_returns["cum_r"]),
        float(kpi_from_equity["cum_r"]),
        rel_tol=1e-6,
        abs_tol=1e-6,
    )
