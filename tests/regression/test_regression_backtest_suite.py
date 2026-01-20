from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.backtest.regression import RegressionBacktestSuite, RegressionDataMismatch
from src.utils.hashing import sha256_path


def _write_bundle(bundle_dir: Path, *, close_values: list[float]) -> Path:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bars_path = bundle_dir / "bars.parquet"
    df = pd.DataFrame({"close": close_values})
    df.to_parquet(bars_path)
    manifest = {
        "bars_path": "bars.parquet",
        "bars_sha256": sha256_path(bars_path),
        "config_hash": "sha256:dummy",
    }
    (bundle_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return bundle_dir


def _write_scenarios(
    path: Path, bundle_path: Path, *, metric_target: float, tolerance: float = 10.0
) -> None:
    path.write_text(
        "\n".join(
            [
                "schema_version: regression.scenario.v1",
                "scenarios:",
                "  - id: scenario-1",
                "    strategy_id: m1_baseline_ma_rsi",
                "    window: 2021-01-01/2021-12-31",
                f"    market_data_bundle: {bundle_path}",
                "    expected_metrics:",
                "      - metric: pf_all",
                f"        target: {metric_target}",
                f"        tolerance: {tolerance}",
            ]
        ),
        encoding="utf-8",
    )


def test_regression_suite_runs(tmp_path: Path, monkeypatch: object) -> None:
    bundle_dir = _write_bundle(tmp_path / "bundle", close_values=[100, 101, 102, 103])
    scenarios_path = tmp_path / "scenarios.yaml"
    _write_scenarios(scenarios_path, bundle_dir, metric_target=1.0)
    monkeypatch.setenv("TRADECTL_PROFILE", "backtest")
    suite = RegressionBacktestSuite(
        scenarios_path=scenarios_path,
        config_path=tmp_path / "regression.yaml",
        output_root=tmp_path / "reports",
        metrics_path=tmp_path / "metrics.jsonl",
    )
    (tmp_path / "regression.yaml").write_text(
        "\n".join(
            [
                "schema_version: regression.v1",
                "max_concurrency: 1",
                "max_runtime_per_scenario_min: 1",
                "scenarios: []",
            ]
        ),
        encoding="utf-8",
    )
    summary = suite.run_all()
    assert summary.status in {"pass", "fail"}
    assert summary.scenarios[0].scenario_id == "scenario-1"


def test_regression_suite_detects_bundle_mismatch(tmp_path: Path) -> None:
    bundle_dir = _write_bundle(tmp_path / "bundle", close_values=[100, 101, 102, 103])
    manifest_path = bundle_dir / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["bars_sha256"] = "sha256:bad"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    scenarios_path = tmp_path / "scenarios.yaml"
    _write_scenarios(scenarios_path, bundle_dir, metric_target=1.0)
    suite = RegressionBacktestSuite(
        scenarios_path=scenarios_path,
        config_path=tmp_path / "regression.yaml",
        output_root=tmp_path / "reports",
        metrics_path=tmp_path / "metrics.jsonl",
    )
    (tmp_path / "regression.yaml").write_text(
        "schema_version: regression.v1\nmax_concurrency: 1\nmax_runtime_per_scenario_min: 1\nscenarios: []\n",
        encoding="utf-8",
    )
    try:
        suite.run_all()
    except RegressionDataMismatch:
        assert True
    else:
        raise AssertionError("RegressionDataMismatch not raised")


def test_regression_suite_flags_drift(tmp_path: Path) -> None:
    bundle_dir = _write_bundle(tmp_path / "bundle", close_values=[100, 101, 102, 103])
    scenarios_path = tmp_path / "scenarios.yaml"
    _write_scenarios(scenarios_path, bundle_dir, metric_target=0.1, tolerance=0.01)
    suite = RegressionBacktestSuite(
        scenarios_path=scenarios_path,
        config_path=tmp_path / "regression.yaml",
        output_root=tmp_path / "reports",
        metrics_path=tmp_path / "metrics.jsonl",
    )
    (tmp_path / "regression.yaml").write_text(
        "schema_version: regression.v1\nmax_concurrency: 1\nmax_runtime_per_scenario_min: 1\nscenarios: []\n",
        encoding="utf-8",
    )
    summary = suite.run_all()
    assert summary.status == "fail"
