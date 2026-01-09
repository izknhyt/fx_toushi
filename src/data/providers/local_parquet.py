"""Local Parquet-backed provider handler for SLA tuning and offline tests."""

from __future__ import annotations

import time
from collections.abc import Sequence
from functools import partial
from pathlib import Path

import pandas as pd

from src.data.service import MarketFrame, ProviderError, ProviderResult

__all__ = ["parquet_provider", "build_parquet_provider"]


def parquet_provider(
    symbols: Sequence[str],
    timeframe: str,
    *,
    base_path: Path = Path("data/provider_cache"),
) -> ProviderResult:
    """Load bars from local Parquet or CSV snapshots to emulate a real provider call."""

    frames: list[MarketFrame] = []
    start = time.perf_counter()
    for symbol in symbols:
        parquet_file = base_path / f"{symbol}_{timeframe}.parquet"
        csv_file = base_path / f"{symbol}_{timeframe}.csv"
        file_path = parquet_file if parquet_file.exists() else csv_file
        if not file_path.exists():
            raise ProviderError(f"local data not found for {symbol} {timeframe}")
        if file_path.suffix.lower() == ".parquet":
            df = pd.read_parquet(file_path)
        else:
            df = pd.read_csv(file_path)
        bars = df.to_dict(orient="records")
        frames.append(MarketFrame(symbol=symbol, timeframe=timeframe, bars=bars, quality_flag=0))
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return ProviderResult(
        frames=frames, p95_ms=elapsed_ms, p99_ms=elapsed_ms * 1.1, rate_limit_ratio=0.0
    )


def build_parquet_provider(*, base_path: Path, timeframe: str):
    """Convenience factory to bind base_path/timeframe ahead of injection."""

    return partial(parquet_provider, base_path=base_path, timeframe=timeframe)
