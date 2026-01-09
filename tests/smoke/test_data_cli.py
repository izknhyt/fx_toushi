"""Smoke tests for new data CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from src.interfaces.cli.data import update_latest


@pytest.mark.smoke
def test_update_latest_from_manifest(tmp_path: Path) -> None:
    manifest_path = Path("reports/data_manifest.json")
    if not manifest_path.exists():
        pytest.skip("data_manifest.json missing")

    results = update_latest(
        symbols=["USDJPY"],
        latest_days=30,
        manifest_path=manifest_path,
        strategy="m1_baseline_ma_rsi",
        merged_override=None,
    )
    assert results
    latest_path = Path(results[0]["latest_path"])
    assert latest_path.exists()


@pytest.mark.smoke
def test_data_update_gap_plan(tmp_path: Path) -> None:
    script = Path("tools/update_market_data.py")
    if not script.exists():
        pytest.skip("update_market_data.py missing")

    # Use a tiny synthetic frame to check command wiring.
    df = pytest.importorskip("pandas").DataFrame(
        {
            "timestamp": ["2025-12-19T00:00:00Z", "2025-12-19T00:10:00Z"],
            "open": [1.0, 1.0],
            "high": [1.0, 1.0],
            "low": [1.0, 1.0],
            "close": [1.0, 1.0],
            "volume": [1.0, 1.0],
        }
    )
    temp_dir = tmp_path / "usd"
    temp_dir.mkdir()
    merged = temp_dir / "usdjpy_m5_20251219_20251219_merged.parquet"
    df.to_parquet(merged, index=False)
    gap_report = tmp_path / "gaps.json"
    plan = tmp_path / "fetch.sh"

    import sys
    from subprocess import run

    result = run(
        [
            sys.executable,
            "tools/update_market_data.py",
            "--symbol",
            "USDJPY",
            "--merged",
            str(merged),
            "--gap-report",
            str(gap_report),
            "--emit-fetch-plan",
            str(plan),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout.strip())
    assert payload["symbol"] == "USDJPY"
    assert gap_report.exists()
    assert plan.exists()
