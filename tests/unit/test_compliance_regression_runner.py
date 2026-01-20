from __future__ import annotations

import json
from pathlib import Path

from tools.compliance_regression import run_regression


def _write_broker_rules(path: Path) -> None:
    payload = "\n".join(
        [
            "schema_version: broker.rules.v1",
            "symbols:",
            "  EURUSD:",
            "    min_lot: 0.1",
            "    lot_step: 0.05",
            "    min_distance_pips:",
            "      stop_loss: 2.0",
            "      take_profit: 2.0",
            "    freeze_level_pips: 1.0",
            "    allowed_time_windows: []",
        ]
    )
    path.write_text(payload + "\n", encoding="utf-8")


def _write_scenarios(path: Path) -> None:
    scenario = {
        "scenario_id": "EURUSD_normal_00",
        "pair": "EURUSD",
        "mode": "paper",
        "timestamp": "2025-03-03T00:10:00Z",
        "spread_pips": 0.2,
        "atr_pips": 0.5,
        "proposed_sl_pips": 1.0,
        "proposed_tp_pips": 1.0,
        "lot": 0.12,
        "reason_tags": ["baseline"],
        "adjustments": {},
    }
    path.write_text(json.dumps(scenario) + "\n", encoding="utf-8")


def test_compliance_regression_counts(tmp_path: Path) -> None:
    rules = tmp_path / "broker_rules.yaml"
    _write_broker_rules(rules)
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "EURUSD.jsonl"
    _write_scenarios(scenario_path)

    result = run_regression(
        profile="paper",
        scenarios_path=scenarios_dir,
        rules_path=rules,
        output_dir=tmp_path / "reports",
        metrics_path=tmp_path / "metrics.json",
        dry_run=False,
    )

    payload = result["result"]
    assert payload["min_distance_violations"] == 1
    assert payload["freeze_level_violations"] == 0
    assert payload["rounding_issues"] == 1
