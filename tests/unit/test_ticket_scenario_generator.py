from __future__ import annotations

import json
from pathlib import Path

from tools.compliance_ticket_generator import TicketScenarioGenerator


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


def _write_scenario(path: Path) -> None:
    payload = {
        "scenario": "normal",
        "spread_pips": [0.1, 0.2],
        "atr_pips": [0.1, 0.2],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_ticket_scenario_generation(tmp_path: Path) -> None:
    rules = tmp_path / "broker_rules.yaml"
    _write_broker_rules(rules)
    scenario_dir = tmp_path / "scenarios"
    scenario_dir.mkdir()
    _write_scenario(scenario_dir / "normal.json")

    generator = TicketScenarioGenerator(broker_rules=rules, scenario_dir=scenario_dir)
    output_dir = generator.write(per_pair=1, mode="paper", seed=1, out_dir=tmp_path / "out")

    scenario_path = output_dir / "EURUSD.jsonl"
    assert scenario_path.exists()
    payload = json.loads(scenario_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["proposed_sl_pips"] >= 2.0
    assert payload["proposed_tp_pips"] >= 2.0
    assert payload["lot"] >= 0.1
    assert payload["lot"] % 0.05 == 0
