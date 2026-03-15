from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.run_long_horizon_portfolio_validation import (
    WINDOW_PROFILES,
    _build_summary_row,
    _load_quality_snapshot,
    _render_summary_md,
    build_plan,
)


def test_load_quality_snapshot_reports_basic_gap_and_duplicate_stats(tmp_path: Path) -> None:
    path = tmp_path / "usdjpy_m5_20160101_20251231_merged.parquet"
    pd.DataFrame(
        {
            "timestamp": [
                "2016-01-01T00:00:00Z",
                "2016-01-01T00:05:00Z",
                "2016-01-01T00:20:00Z",
                "2016-01-01T00:20:00Z",
            ],
            "open": [120.0, 120.1, 120.2, 120.2],
            "high": [120.1, 120.2, 120.3, 120.3],
            "low": [119.9, 120.0, 120.1, 120.1],
            "close": [120.05, 120.15, 120.25, 120.25],
            "volume": [1, 1, 1, 1],
        }
    ).to_parquet(path, index=False)

    payload = _load_quality_snapshot(path, expected_minutes=5)

    assert payload["rows"] == 4
    assert payload["gap_count"] == 1
    assert payload["max_gap_minutes"] == 15
    assert payload["duplicate_timestamp_count"] == 1


def test_build_plan_uses_explicit_data_path_and_window_profile(tmp_path: Path) -> None:
    merged = tmp_path / "merged.parquet"
    pd.DataFrame(
        {
            "timestamp": ["2016-01-01T00:00:00Z", "2025-12-31T23:55:00Z"],
            "open": [120.0, 150.0],
            "high": [120.1, 150.1],
            "low": [119.9, 149.9],
            "close": [120.05, 150.05],
            "volume": [1, 1],
        }
    ).to_parquet(merged, index=False)

    payload = build_plan(
        manifest_path=Path("config/strategy_manifest.parallel_portfolio_v2.yaml"),
        allocation_config_path=Path("config/strategy_allocation.yaml"),
        allocation_profile="portfolio_admission_v2",
        symbol="USDJPY",
        data_path=merged,
        expected_minutes=5,
        window_profile="usd_jpy_long_horizon",
    )

    assert payload["allocation_profile"] == "portfolio_admission_v2"
    assert payload["data_quality"]["path"] == str(merged)
    assert [item["name"] for item in payload["windows"]] == [
        window.name for window in WINDOW_PROFILES["usd_jpy_long_horizon"]
    ]


def test_render_summary_md_lists_window_rows() -> None:
    window = WINDOW_PROFILES["usd_jpy_long_horizon"][0]
    report = {
        "summary": {"pf": 1.25, "avg_r": 0.08, "win_rate": 0.5, "count": 321},
        "metrics": {"max_drawdown_all": 0.11},
        "acceptance_gate": {"status": "pass", "checks": {"pf_min_1_10": True}},
    }
    row = _build_summary_row(
        window=window,
        report=report,
        raw_path=Path("reports/validation_log/raw.json"),
        report_json_path=Path("reports/analysis/report.json"),
        report_md_path=Path("reports/analysis/report.md"),
    )
    payload = {
        "generated_at_utc": "2026-03-14T11:00:00+00:00",
        "manifest_path": "config/strategy_manifest.parallel_portfolio_v2.yaml",
        "allocation_profile": "portfolio_admission_v2",
        "fixed_assumptions": {"symbols": ["USDJPY"]},
        "data_quality": {
            "path": "data/research/curated/usdjpy/usdjpy_m5_20160101_20251231_merged.parquet",
            "rows": 100,
            "start": "2016-01-01T00:00:00+00:00",
            "end": "2025-12-31T23:55:00+00:00",
            "gap_count": 0,
            "max_gap_minutes": 0,
            "duplicate_timestamp_count": 0,
        },
        "results": [row],
    }

    rendered = _render_summary_md(payload)

    assert "# Long-Horizon Portfolio Validation" in rendered
    assert "2016_2025" in rendered
    assert "1.25" in rendered
    assert "pass" in rendered
