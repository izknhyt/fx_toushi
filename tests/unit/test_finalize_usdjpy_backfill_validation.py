from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from tools.finalize_usdjpy_backfill_validation import (
    assess_backfill_readiness,
    build_merge_command,
    build_validation_command,
)


def test_assess_backfill_readiness_pending_when_merged_start_is_after_target(tmp_path: Path) -> None:
    merged = tmp_path / "usdjpy_m5_20210101_20260225_merged.parquet"
    pd.DataFrame({"timestamp": ["2021-01-01T00:00:00Z"]}).to_parquet(merged, index=False)

    result = assess_backfill_readiness(
        symbol="USDJPY",
        target_start=date(2016, 1, 1),
        merged_path=merged,
    )

    assert result.status == "pending_backfill"
    assert result.ready is False
    assert result.merged_start == "2021-01-01"


def test_assess_backfill_readiness_ready_when_merged_start_reaches_target(tmp_path: Path) -> None:
    merged = tmp_path / "usdjpy_m5_20160101_20260225_merged.parquet"
    pd.DataFrame({"timestamp": ["2016-01-01T00:00:00Z", "2026-02-25T11:20:00Z"]}).to_parquet(
        merged, index=False
    )

    result = assess_backfill_readiness(
        symbol="USDJPY",
        target_start=date(2016, 1, 1),
        merged_path=merged,
    )

    assert result.status == "ready"
    assert result.ready is True


def test_build_merge_command_includes_manifest_refresh_and_gap_report(tmp_path: Path) -> None:
    cmd = build_merge_command(
        symbol="USDJPY",
        source_dir=tmp_path / "curated" / "usdjpy",
        latest_days=120,
        gap_report=tmp_path / "gap.json",
    )

    assert "tools/update_market_data.py" in cmd
    assert "--update-manifest" in cmd
    assert "--gap-report" in cmd
    assert "--gap-exclude-weekend" in cmd


def test_build_validation_command_runs_long_horizon_tool(tmp_path: Path) -> None:
    cmd = build_validation_command(
        manifest_path=tmp_path / "manifest.yaml",
        allocation_config_path=tmp_path / "allocation.yaml",
        allocation_profile="portfolio_admission_v2",
        data_path=tmp_path / "merged.parquet",
        plan_json=tmp_path / "plan.json",
        summary_md=tmp_path / "summary.md",
    )

    assert "tools/run_long_horizon_portfolio_validation.py" in cmd
    assert "--run" in cmd
    assert "--allocation-profile" in cmd
    assert "portfolio_admission_v2" in cmd
