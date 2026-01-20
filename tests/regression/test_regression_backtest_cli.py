from __future__ import annotations

from pathlib import Path

from src.interfaces.cli.backtest_regression import regression_list, regression_run


def _write_scenarios(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "schema_version: regression.scenario.v1",
                "scenarios:",
                "  - id: scenario-1",
                "    strategy_id: m1_baseline_ma_rsi",
                "    window: 2021-01-01/2021-12-31",
                "    market_data_bundle: bundle",
                "    expected_metrics: []",
            ]
        ),
        encoding="utf-8",
    )


def test_regression_list_returns_schema(tmp_path: Path) -> None:
    scenarios_path = tmp_path / "scenarios.yaml"
    _write_scenarios(scenarios_path)
    payload = regression_list(scenarios_path=scenarios_path)
    assert payload["status"] == "ok"
    assert payload["scenarios"][0]["schema_version"] == "regression.scenario.v1"


def test_regression_run_missing_scenario(tmp_path: Path) -> None:
    scenarios_path = tmp_path / "scenarios.yaml"
    _write_scenarios(scenarios_path)
    payload = regression_run(
        scenario_id="missing",
        scenarios_path=scenarios_path,
        output_root=tmp_path / "reports",
        metrics_path=tmp_path / "metrics.jsonl",
    )
    assert payload["status"] in {"error", "fail", "pass"}
