from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from tools.run_long_horizon_portfolio_validation import (
    WINDOW_PROFILES,
    _build_summary_row,
    _effective_manifest_output_path,
    _load_quality_snapshot,
    _load_strategy_overrides,
    _materialize_strategy_subset_manifest,
    _materialize_override_manifest,
    _resolve_strategy_ids,
    _resolve_windows,
    _render_summary_md,
    _yaml_dump_text,
    build_plan,
)


def _write_yaml(path: Path, payload: dict[str, object]) -> None:
    path.write_text(_yaml_dump_text(payload), encoding="utf-8")


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


def test_build_plan_filters_windows_when_subset_is_requested(tmp_path: Path) -> None:
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
        selected_windows=("2016_2021", "2016_2025"),
    )

    assert payload["selected_windows"] == ["2016_2025", "2016_2021"]
    assert [item["name"] for item in payload["windows"]] == ["2016_2025", "2016_2021"]


def test_resolve_windows_rejects_unknown_subset_name() -> None:
    try:
        _resolve_windows(
            window_profile="usd_jpy_long_horizon",
            selected_names=("missing_window",),
        )
    except ValueError as exc:
        assert "missing_window" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ValueError")


def test_build_plan_filters_strategy_subset_when_requested(tmp_path: Path) -> None:
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

    manifest = tmp_path / "manifest.yaml"
    _write_yaml(
        manifest,
        {
            "strategies": {
                "alpha": {"enabled": True},
                "beta": {"enabled": True},
                "gamma": {"enabled": False},
            }
        },
    )

    payload = build_plan(
        manifest_path=manifest,
        allocation_config_path=Path("config/strategy_allocation.yaml"),
        allocation_profile="portfolio_admission_v2",
        symbol="USDJPY",
        data_path=merged,
        expected_minutes=5,
        window_profile="usd_jpy_long_horizon",
        selected_strategy_ids=("beta", "alpha"),
    )

    assert payload["selected_strategy_ids"] == ["alpha", "beta"]


def test_build_plan_records_strategy_override_ids(tmp_path: Path) -> None:
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
    manifest = tmp_path / "manifest.yaml"
    _write_yaml(manifest, {"strategies": {"alpha": {"enabled": True}, "beta": {"enabled": True}}})
    overrides = tmp_path / "overrides.yaml"
    _write_yaml(overrides, {"beta": {"parameters": {"entry": {"filters": {"atr_min": 0.1}}}}})

    payload = build_plan(
        manifest_path=manifest,
        allocation_config_path=Path("config/strategy_allocation.yaml"),
        allocation_profile="portfolio_admission_v2",
        symbol="USDJPY",
        data_path=merged,
        expected_minutes=5,
        window_profile="usd_jpy_long_horizon",
        strategy_overrides_path=overrides,
    )

    assert payload["strategy_override_ids"] == ["beta"]
    assert payload["strategy_overrides_path"] == str(overrides)


def test_resolve_strategy_ids_rejects_unknown_strategy(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    _write_yaml(manifest, {"strategies": {"alpha": {"enabled": True}}})

    try:
        _resolve_strategy_ids(manifest_path=manifest, selected_ids=("missing",))
    except ValueError as exc:
        assert "missing" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ValueError")


def test_load_strategy_overrides_rejects_non_mapping_value(tmp_path: Path) -> None:
    overrides = tmp_path / "overrides.yaml"
    _write_yaml(overrides, {"alpha": True})

    try:
        _load_strategy_overrides(overrides)
    except ValueError as exc:
        assert "alpha" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ValueError")


def test_materialize_strategy_subset_manifest_disables_unselected_entries(tmp_path: Path) -> None:
    source = tmp_path / "source.yaml"
    _write_yaml(
        source,
        {
            "manifest_name": "Example",
            "notes": "base",
            "strategies": {
                "alpha": {"enabled": True, "weight": 0.5},
                "beta": {"enabled": True, "weight": 0.5},
            },
        },
    )

    output = _materialize_strategy_subset_manifest(
        source_manifest_path=source,
        selected_strategy_ids=("beta",),
        strategy_overrides=None,
        output_path=tmp_path / "subset.yaml",
    )
    payload = yaml.safe_load(output.read_text(encoding="utf-8"))

    assert payload["strategies"]["alpha"]["enabled"] is False
    assert payload["strategies"]["beta"]["enabled"] is True
    assert "[subset]" in payload["manifest_name"]
    assert "Focused validation subset: beta" in payload["notes"]


def test_materialize_strategy_subset_manifest_applies_overrides(tmp_path: Path) -> None:
    source = tmp_path / "source.yaml"
    _write_yaml(
        source,
        {
            "strategies": {
                "alpha": {"enabled": True, "parameters": {"entry": {"filters": {"atr_min": 0.08}}}},
                "beta": {"enabled": True, "parameters": {"entry": {"filters": {"atr_min": 0.08}}}},
            }
        },
    )

    output = _materialize_strategy_subset_manifest(
        source_manifest_path=source,
        selected_strategy_ids=("beta",),
        strategy_overrides={"beta": {"parameters": {"entry": {"filters": {"atr_min": 0.12}}}}},
        output_path=tmp_path / "subset_override.yaml",
    )
    payload = yaml.safe_load(output.read_text(encoding="utf-8"))

    assert payload["strategies"]["alpha"]["enabled"] is False
    assert payload["strategies"]["beta"]["parameters"]["entry"]["filters"]["atr_min"] == 0.12
    assert "Focused validation overrides: beta" in payload["notes"]


def test_materialize_override_manifest_applies_without_strategy_subset(tmp_path: Path) -> None:
    source = tmp_path / "source.yaml"
    _write_yaml(
        source,
        {
            "strategies": {
                "alpha": {"enabled": True, "parameters": {"entry": {"filters": {"atr_min": 0.08}}}},
                "beta": {"enabled": True, "parameters": {"entry": {"filters": {"atr_min": 0.08}}}},
            }
        },
    )

    output = _materialize_override_manifest(
        source_manifest_path=source,
        strategy_overrides={"alpha": {"parameters": {"entry": {"filters": {"atr_min": 0.11}}}}},
        output_path=tmp_path / "override.yaml",
    )
    payload = yaml.safe_load(output.read_text(encoding="utf-8"))

    assert payload["strategies"]["alpha"]["parameters"]["entry"]["filters"]["atr_min"] == 0.11
    assert payload["strategies"]["beta"]["parameters"]["entry"]["filters"]["atr_min"] == 0.08
    assert "[override]" in payload["manifest_name"]


def test_effective_manifest_output_path_is_persistent_validation_artifact() -> None:
    output = _effective_manifest_output_path(stamp="20260315T132308Z", variant="subset")

    assert output.name == "long_horizon_portfolio_20260315T132308Z_effective_manifest.focused.yaml"
    assert output.parent.name == "validation_log"


def test_render_summary_md_lists_window_rows() -> None:
    window = WINDOW_PROFILES["usd_jpy_long_horizon"][0]
    report = {
        "summary": {"pf": 1.25, "avg_r": 0.08, "win_rate": 0.5, "count": 321},
        "metrics": {"max_drawdown": 0.11},
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
        "selected_strategy_ids": ["m1_asia_compression_expansion_breakout"],
        "strategy_override_ids": ["m1_asia_compression_expansion_breakout"],
        "strategy_overrides_path": "/tmp/overrides.yaml",
        "effective_manifest_path": "/tmp/strategy_manifest.focused.yaml",
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
    assert "0.11" in rendered
    assert "m1_asia_compression_expansion_breakout" in rendered
    assert "/tmp/overrides.yaml" in rendered
    assert "/tmp/strategy_manifest.focused.yaml" in rendered
