from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.benchmark.ingest import BenchmarkIngestor


def test_benchmark_ingest_dedup_and_fill(tmp_path: Path) -> None:
    csv_path = tmp_path / "benchmark.csv"
    frame = pd.DataFrame(
        {
            "timestamp": [
                "2025-01-01T00:00:00Z",
                "2025-01-01T02:00:00Z",
                "2025-01-01T02:00:00Z",
            ],
            "close": [1.0, 1.2, 1.25],
        }
    )
    frame.to_csv(csv_path, index=False)
    out_dir = tmp_path / "benchmark_runs" / "raw"
    ingestor = BenchmarkIngestor(output_dir=out_dir)
    result = ingestor.ingest(
        provider="tradingview",
        path=csv_path,
        mode="paper",
        symbol="USDJPY",
        timeframe="1h",
    )
    assert result.duplicates_dropped == 1
    assert result.missing_filled == 1
    assert result.output_path is not None
    assert result.output_path.exists()
    assert result.output_path.name.endswith("_usdjpy_1h_paper.parquet")
    loaded = pd.read_parquet(result.output_path)
    assert len(loaded) == 3
