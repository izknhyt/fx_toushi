from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


def test_update_market_data_ignores_non_m5_sources(tmp_path: Path) -> None:
    source_dir = tmp_path / "curated" / "usdjpy"
    source_dir.mkdir(parents=True)

    pd.DataFrame(
        {
            "timestamp": ["2026-02-09T09:00:00Z", "2026-02-09T09:05:00Z"],
            "open": [150.1, 150.2],
            "high": [150.2, 150.3],
            "low": [150.0, 150.1],
            "close": [150.15, 150.25],
            "volume": [100, 120],
        }
    ).to_parquet(source_dir / "usdjpy_m5_20260209_20260209.parquet", index=False)

    # This file is intentionally incompatible and should be ignored.
    pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]}).to_parquet(
        source_dir / "usdjpy_d1_20240101_20241231_dukascopy.parquet",
        index=False,
    )

    result = subprocess.run(
        [
            sys.executable,
            "tools/update_market_data.py",
            "--symbol",
            "USDJPY",
            "--source-dir",
            str(source_dir),
            "--write-latest",
            "--latest-days",
            "30",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout.strip())
    merged_path = Path(payload["merged"])
    assert merged_path.exists()
    merged = pd.read_parquet(merged_path)
    assert len(merged) == 2
    assert set(["timestamp", "open", "high", "low", "close", "volume"]).issubset(merged.columns)


def test_update_market_data_normalizes_price_scales_and_uses_latest_ts_column(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "curated" / "usdjpy"
    source_dir.mkdir(parents=True)

    # Legacy source with decimal scale (1.55xx) that should be normalized to 155.xx.
    pd.DataFrame(
        {
            "timestamp": ["2025-12-01T00:00:00Z", "2025-12-01T00:05:00Z"],
            "open": [1.5540, 1.5550],
            "high": [1.5550, 1.5560],
            "low": [1.5530, 1.5540],
            "close": [1.5545, 1.5555],
            "volume": [10, 10],
        }
    ).to_parquet(source_dir / "usdjpy_m5_20251201_20251201_dukascopy.parquet", index=False)

    # Broken large-scale source (around 75k) should be normalized to FX price scale.
    pd.DataFrame(
        {
            "timestamp": ["2025-12-02T00:00:00Z"],
            "open": [77700.0],
            "high": [77800.0],
            "low": [77600.0],
            "close": [77750.0],
            "volume": [5],
        }
    ).to_parquet(source_dir / "usdjpy_5m_20251202_20251202_dukascopy.parquet", index=False)

    # Latest file arrives with only ts populated.
    pd.DataFrame(
        {
            "timestamp": [None, None],
            "ts": ["2026-02-09T12:15:00Z", "2026-02-09T12:20:00Z"],
            "open": [156.41, 156.42],
            "high": [156.46, 156.53],
            "low": [156.38, 156.40],
            "close": [156.41, 156.51],
            "volume": [1, 1],
        }
    ).to_parquet(source_dir / "usdjpy_m5_latest.parquet", index=False)

    result = subprocess.run(
        [
            sys.executable,
            "tools/update_market_data.py",
            "--symbol",
            "USDJPY",
            "--source-dir",
            str(source_dir),
            "--write-latest",
            "--latest-days",
            "120",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout.strip())
    merged = pd.read_parquet(Path(payload["merged"]))
    merged["timestamp"] = pd.to_datetime(merged["timestamp"], utc=True, errors="coerce")

    assert merged["timestamp"].max() == pd.Timestamp("2026-02-09T12:20:00Z")
    assert merged["close"].between(100.0, 200.0).all()
