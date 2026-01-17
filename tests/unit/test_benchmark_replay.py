from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.benchmark.replay import (
    BenchmarkReplayGapError,
    BenchmarkReplayService,
)


def _write_returns(path: Path) -> None:
    frame = pd.DataFrame(
        {
            "timestamp": [
                "2025-01-01T00:00:00Z",
                "2025-01-02T00:00:00Z",
                "2025-01-03T00:00:00Z",
            ],
            "return": [0.01, -0.005, 0.02],
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _write_benchmark(path: Path) -> None:
    frame = pd.DataFrame(
        {
            "timestamp": [
                "2025-01-01T00:00:00Z",
                "2025-01-02T00:00:00Z",
                "2025-01-03T00:00:00Z",
            ],
            "close": [1.0, 1.01, 1.03],
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def test_benchmark_replay_generates_report(tmp_path: Path) -> None:
    strategy_path = tmp_path / "reports" / "performance" / "paper" / "returns.csv"
    benchmark_path = tmp_path / "benchmark_runs" / "raw" / "tradingview" / "20250101.csv"
    _write_returns(strategy_path)
    _write_benchmark(benchmark_path)
    service = BenchmarkReplayService(
        strategy_base=tmp_path / "reports" / "performance",
        benchmark_raw_dir=tmp_path / "benchmark_runs" / "raw",
        output_dir=tmp_path / "benchmark_runs",
        report_dir=tmp_path / "reports" / "benchmark",
        threshold_config=tmp_path / "config" / "benchmark_monitor.yaml",
    )
    report_path = tmp_path / "reports" / "benchmark" / "sample.md"
    result = service.replay(
        window="3d",
        mode="paper",
        providers=["tradingview"],
        export_path=report_path,
    )
    assert result.status == "ok"
    assert result.output_path is not None
    assert Path(result.output_path).exists()
    assert result.report_path == str(report_path)
    assert report_path.exists()


def test_benchmark_replay_gap_error(tmp_path: Path) -> None:
    strategy_path = tmp_path / "reports" / "performance" / "paper" / "returns.csv"
    _write_returns(strategy_path)
    threshold_path = tmp_path / "config" / "benchmark_monitor.yaml"
    threshold_path.parent.mkdir(parents=True, exist_ok=True)
    threshold_path.write_text('{"missing_ratio_threshold": 0.0}\n', encoding="utf-8")
    service = BenchmarkReplayService(
        strategy_base=tmp_path / "reports" / "performance",
        benchmark_raw_dir=tmp_path / "benchmark_runs" / "raw",
        output_dir=tmp_path / "benchmark_runs",
        report_dir=tmp_path / "reports" / "benchmark",
        threshold_config=threshold_path,
    )
    with pytest.raises(BenchmarkReplayGapError):
        service.replay(window="3d", mode="paper", fail_on_gap=True)
