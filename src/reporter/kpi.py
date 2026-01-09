"""Lightweight KPI computation helpers for weekly reports."""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path

import pandas as pd

__all__ = ["compute_kpi_from_returns", "compute_kpi_from_equity"]


def compute_kpi_from_returns(path: Path) -> Mapping[str, object]:
    """Compute Sharpe/Max DD/Win Rate/Cumulative R from a returns file."""

    if not path.exists():
        return {"sharpe": "n/a", "max_dd": "n/a", "win_rate": "n/a", "cum_r": "n/a"}
    frame = _load_frame(path)
    if frame.empty:
        return {"sharpe": "n/a", "max_dd": "n/a", "win_rate": "n/a", "cum_r": "n/a"}
    returns = frame["r"].astype(float)
    mean = returns.mean()
    std = returns.std(ddof=0)
    sharpe = mean / std * math.sqrt(len(returns)) if std > 0 else 0.0
    equity = (1 + returns).cumprod()
    peak = equity.cummax()
    drawdown = (equity - peak) / peak
    max_dd = abs(drawdown.min()) if not drawdown.empty else 0.0
    win_rate = (returns > 0).mean()
    cum_r = returns.sum()
    return {
        "sharpe": round(sharpe, 4),
        "max_dd": round(max_dd, 4),
        "win_rate": round(win_rate, 4),
        "cum_r": round(cum_r, 4),
    }


def compute_kpi_from_equity(path: Path) -> Mapping[str, object]:
    """Compute KPI from equity curve by deriving returns."""

    if not path.exists():
        return {"sharpe": "n/a", "max_dd": "n/a", "win_rate": "n/a", "cum_r": "n/a"}
    frame = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    equity_col = None
    for candidate in ("equity", "balance", "equity_curve"):
        if candidate in frame.columns:
            equity_col = candidate
            break
    if equity_col is None:
        return {"sharpe": "n/a", "max_dd": "n/a", "win_rate": "n/a", "cum_r": "n/a"}
    equity = frame[equity_col].astype(float)
    returns = equity.pct_change().dropna()
    returns.name = "r"
    tmp = path.with_suffix(".returns.tmp.parquet")
    returns.to_frame().to_parquet(tmp)
    return compute_kpi_from_returns(tmp)


def _load_frame(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    frame = pd.read_parquet(path) if suffix == ".parquet" else pd.read_csv(path)
    if "r" not in frame.columns and "return" in frame.columns:
        frame = frame.rename(columns={"return": "r"})
    if "r" not in frame.columns:
        raise ValueError("Returns file must contain 'r' column")
    return frame
