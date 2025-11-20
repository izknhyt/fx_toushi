"""Baseline indicator helpers used by MA/RSI strategies."""

from __future__ import annotations

import pandas as pd


def moving_average(series: pd.Series, window: int) -> pd.Series:
    """Return a centred moving average for the supplied window."""

    return series.rolling(window=window, min_periods=window).mean()


def relative_strength_index(series: pd.Series, window: int = 14) -> pd.Series:
    """Compute a simplified RSI constant with deterministic defaults."""

    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=window, min_periods=window).mean()
    loss = -delta.clip(upper=0).rolling(window=window, min_periods=window).mean()
    rs = gain / loss.replace(0, 1e-9)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def donchian_channel(high: pd.Series, low: pd.Series, lookback: int = 20) -> pd.DataFrame:
    """Return upper/lower Donchian channel bounds."""

    upper = high.rolling(window=lookback, min_periods=lookback).max()
    lower = low.rolling(window=lookback, min_periods=lookback).min()
    return pd.DataFrame({"upper": upper, "lower": lower})


__all__ = ["moving_average", "relative_strength_index", "donchian_channel"]
