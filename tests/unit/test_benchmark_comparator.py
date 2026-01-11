from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.reporter.benchmark import BenchmarkComparator, BenchmarkGapError


def _write_returns(path: Path, ts: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame({"ts": ts, "r": [0.01] * len(ts)})
    frame.to_parquet(path)


def test_benchmark_compare_raises_on_missing_ratio(tmp_path: Path) -> None:
    strategy_path = tmp_path / "reports" / "performance" / "paper" / "returns.parquet"
    benchmark_path = tmp_path / "benchmark_runs" / "normalized" / "alpha_paper.parquet"
    _write_returns(strategy_path, [f"2025-01-{day:02d}" for day in range(1, 11)])
    _write_returns(benchmark_path, [f"2025-01-{day:02d}" for day in range(1, 9)])

    comparator = BenchmarkComparator(
        strategy_base=tmp_path / "reports" / "performance",
        benchmark_dir=tmp_path / "benchmark_runs" / "normalized",
        compare_log=tmp_path / "logs" / "benchmark" / "compare.jsonl",
        event_log=tmp_path / "logs" / "events" / "benchmark_gap.jsonl",
    )

    with pytest.raises(BenchmarkGapError) as excinfo:
        comparator.compare(window="90d", mode="paper", providers=["alpha"])

    assert excinfo.value.result.status == "gap"
    assert excinfo.value.event["event"] == "benchmark_gap"


def test_benchmark_compare_ok_when_coverage_complete(tmp_path: Path) -> None:
    strategy_path = tmp_path / "reports" / "performance" / "paper" / "returns.parquet"
    benchmark_path = tmp_path / "benchmark_runs" / "normalized" / "alpha_paper.parquet"
    ts = [f"2025-02-{day:02d}" for day in range(1, 11)]
    _write_returns(strategy_path, ts)
    _write_returns(benchmark_path, ts)

    comparator = BenchmarkComparator(
        strategy_base=tmp_path / "reports" / "performance",
        benchmark_dir=tmp_path / "benchmark_runs" / "normalized",
        compare_log=tmp_path / "logs" / "benchmark" / "compare.jsonl",
        event_log=tmp_path / "logs" / "events" / "benchmark_gap.jsonl",
    )
    result = comparator.compare(window="90d", mode="paper", providers=["alpha"])

    assert result.status == "ok"
    assert result.missing_ratio == 0.0
    assert result.metrics["sharpe"]["strategy"] is not None
