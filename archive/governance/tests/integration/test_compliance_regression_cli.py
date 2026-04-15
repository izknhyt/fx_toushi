from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli.compliance import regression_diff, regression_generate, regression_run


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


def _write_scenario_dir(tmp_path: Path) -> Path:
    scenario_dir = tmp_path / "scenarios"
    scenario_dir.mkdir()
    scenario = {
        "scenario_id": "EURUSD_normal_00",
        "pair": "EURUSD",
        "mode": "paper",
        "timestamp": "2025-03-03T00:10:00Z",
        "spread_pips": 0.2,
        "atr_pips": 0.5,
        "proposed_sl_pips": 2.5,
        "proposed_tp_pips": 2.5,
        "lot": 0.1,
        "reason_tags": ["baseline"],
        "adjustments": {},
    }
    (scenario_dir / "EURUSD.jsonl").write_text(json.dumps(scenario) + "\n", encoding="utf-8")
    return scenario_dir


def test_compliance_regression_cli_flow(tmp_path: Path, monkeypatch: object) -> None:
    rules_path = tmp_path / "broker_rules.yaml"
    _write_broker_rules(rules_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "broker_rules.yaml").write_text(
        rules_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    market_dir = tmp_path / "data" / "market_scenarios"
    market_dir.mkdir(parents=True, exist_ok=True)
    (market_dir / "normal.json").write_text(
        json.dumps({"scenario": "normal", "spread_pips": [0.1, 0.2], "atr_pips": [0.5, 0.8]}),
        encoding="utf-8",
    )

    out_dir = tmp_path / "generated"
    payload = regression_generate(per_pair=1, profile="paper", out_dir=out_dir, seed=1)
    assert payload["status"] == "ok"

    scenario_dir = _write_scenario_dir(tmp_path)
    run = regression_run(
        profile="paper",
        scenarios=scenario_dir,
        rules_path=tmp_path / "config" / "broker_rules.yaml",
        output_dir=tmp_path / "reports",
        metrics_path=tmp_path / "metrics.json",
        dry_run=False,
    )
    assert run["status"] == "ok"

    current = Path(run["result"]["generated_at"]) if False else tmp_path / "metrics.json"
    against = tmp_path / "metrics_prev.json"
    against.write_text(json.dumps(run["result"], ensure_ascii=False), encoding="utf-8")
    diff = regression_diff(current=tmp_path / "metrics.json", against=against, threshold=0.5)
    assert diff["status"] in {"ok", "threshold_exceeded"}
