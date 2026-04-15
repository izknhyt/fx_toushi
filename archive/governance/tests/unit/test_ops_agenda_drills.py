from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from src.core.gate import GateState
from src.ops.agenda import OpsAgendaService


def _write_plan(path: Path, plan_id: str, scenario_id: str, scheduled_for: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "plan_id": plan_id,
        "scenario_id": scenario_id,
        "scheduled_for": scheduled_for.isoformat().replace("+00:00", "Z"),
        "owner": "ops",
        "board_mode_on_start": "guarded",
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload))
        handle.write("\n")


def test_agenda_filters_pending_drills_under_guarded(tmp_path: Path) -> None:
    template_path = tmp_path / "docs" / "templates" / "daily_agenda.md"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(
        "# Agenda {{agenda.date}}\n\n{{#drill_pending}}- {{plan_id}} {{scenario_id}}\n{{/drill_pending}}\n",
        encoding="utf-8",
    )

    scenarios_path = tmp_path / "config" / "ops" / "drill_scenarios.yaml"
    scenarios_path.parent.mkdir(parents=True, exist_ok=True)
    scenarios_path.write_text(
        "\n".join(
            [
                "scenarios:",
                "  - scenario_id: critical-01",
                "    impact_tags:",
                "      - critical",
                "  - scenario_id: normal-01",
                "    impact_tags:",
                "      - ops",
                "",
            ]
        ),
        encoding="utf-8",
    )

    plans_log = tmp_path / "logs" / "ops" / "drill_plan.jsonl"
    scheduled_for = datetime(2026, 1, 12, tzinfo=timezone.utc)
    _write_plan(plans_log, "plan-critical", "critical-01", scheduled_for)
    _write_plan(plans_log, "plan-normal", "normal-01", scheduled_for)

    gate_state_path = tmp_path / "snapshots" / "latest" / "gate_state.json"
    gate_state_path.parent.mkdir(parents=True, exist_ok=True)
    GateState(auto_execute=False).dump(gate_state_path)

    event_log_path = tmp_path / "logs" / "events" / "ops.agenda.jsonl"

    service = OpsAgendaService(
        template_path=template_path,
        output_dir=tmp_path / "docs" / "runbooks" / "daily_agenda",
        drill_plans_log=plans_log,
        drill_executions_log=tmp_path / "logs" / "ops" / "drill_execution.jsonl",
        scenarios_catalog=scenarios_path,
        gate_state_path=gate_state_path,
        event_log_path=event_log_path,
    )

    ctx = service.build_context(target_date=date(2026, 1, 12))
    assert len(ctx.drill_pending) == 1
    assert ctx.drill_pending[0]["plan_id"] == "plan-critical"
    assert len(ctx.deferred_drills) == 1

    output = service.generate(target_date=date(2026, 1, 12))
    content = output.read_text(encoding="utf-8")
    assert "plan-critical" in content
    assert "plan-normal" not in content

    event_lines = event_log_path.read_text(encoding="utf-8").splitlines()
    assert any("ops.agenda.deferred" in line for line in event_lines)
