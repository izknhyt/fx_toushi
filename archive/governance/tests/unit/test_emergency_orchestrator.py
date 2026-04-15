from __future__ import annotations

from pathlib import Path

from src.emergency.orchestrator import (
    EmergencyContext,
    EmergencyOrchestrator,
    PlaybookRegistry,
)


def test_emergency_orchestrator_trigger_ack_complete(tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "emergency.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "playbooks:",
                "  - id: PB-DATA-STOP",
                "    trigger: data.latency_alert",
                "    runbook_refs: [RUN-DATA-05, RUN-DATA-06]",
                "    action_sequence: [guarded_prompt, kill_switch_review]",
            ]
        ),
        encoding="utf-8",
    )

    registry = PlaybookRegistry(config_path=config_path)
    orchestrator = EmergencyOrchestrator(
        registry=registry,
        state_path=tmp_path / "data" / "emergency" / "state.json",
        event_log=tmp_path / "logs" / "events" / "emergency_playbook.jsonl",
        audit_log=tmp_path / "logs" / "audit" / "emergency.jsonl",
    )
    context = EmergencyContext(health_state="degraded", kill_switch="soft_stop", board_mode="guarded")
    result = orchestrator.trigger(trigger="data.latency_alert", context=context, actor="tester")
    assert result["status"] == "triggered"
    playbook_id = result["playbook"]["playbook_id"]

    ack = orchestrator.ack(playbook_id, actor="ops")
    assert ack["status"] == "ok"

    completed = orchestrator.complete(playbook_id, actor="ops")
    assert completed["status"] == "ok"
