from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def test_degradation_cli_flow(tmp_path: Path, monkeypatch) -> None:
    app = create_cli_app()
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    trigger_result = runner.invoke(
        app,
        [
            "ops",
            "degrade",
            "trigger",
            "--scenario",
            "data_latency",
            "--severity",
            "high",
            "--json",
            "--playbook-dir",
            str(tmp_path / "reports" / "ops" / "degradation_playbooks"),
            "--event-log",
            str(tmp_path / "logs" / "events" / "degradation.jsonl"),
            "--shadow-event-log",
            str(tmp_path / "logs" / "events" / "shadow.jsonl"),
            "--audit-log",
            str(tmp_path / "logs" / "audit" / "degradation.jsonl"),
            "--metrics-path",
            str(tmp_path / "metrics" / "degradation_playbook.jsonl"),
            "--validation-playbook",
            str(tmp_path / "docs" / "validation_playbook" / "AC34_degradation.yaml"),
            "--evidence-ledger",
            str(tmp_path / "logs" / "audit" / "evidence.jsonl"),
            "--ops-worklog",
            str(tmp_path / "ops_worklog.jsonl"),
        ],
    )
    assert trigger_result.exit_code == 0, trigger_result.stdout
    payload = json.loads(trigger_result.stdout)
    instance_id = payload["instance"]["instance_id"]
    node_id = payload["instance"]["nodes"][0]["node_id"]

    evidence = tmp_path / "evidence.md"
    evidence.write_text("ok\n", encoding="utf-8")
    ack_result = runner.invoke(
        app,
        [
            "ops",
            "degrade",
            "ack",
            "--instance",
            instance_id,
            "--node",
            node_id,
            "--evidence",
            str(evidence),
            "--json",
            "--playbook-dir",
            str(tmp_path / "reports" / "ops" / "degradation_playbooks"),
            "--event-log",
            str(tmp_path / "logs" / "events" / "degradation.jsonl"),
            "--shadow-event-log",
            str(tmp_path / "logs" / "events" / "shadow.jsonl"),
            "--audit-log",
            str(tmp_path / "logs" / "audit" / "degradation.jsonl"),
            "--metrics-path",
            str(tmp_path / "metrics" / "degradation_playbook.jsonl"),
            "--validation-playbook",
            str(tmp_path / "docs" / "validation_playbook" / "AC34_degradation.yaml"),
            "--evidence-ledger",
            str(tmp_path / "logs" / "audit" / "evidence.jsonl"),
            "--ops-worklog",
            str(tmp_path / "ops_worklog.jsonl"),
        ],
    )
    assert ack_result.exit_code == 0, ack_result.stdout

    report = tmp_path / "report.md"
    report.write_text("ok\n", encoding="utf-8")
    recover_result = runner.invoke(
        app,
        [
            "ops",
            "degrade",
            "recover",
            "--instance",
            instance_id,
            "--attach-report",
            str(report),
            "--json",
            "--playbook-dir",
            str(tmp_path / "reports" / "ops" / "degradation_playbooks"),
            "--event-log",
            str(tmp_path / "logs" / "events" / "degradation.jsonl"),
            "--shadow-event-log",
            str(tmp_path / "logs" / "events" / "shadow.jsonl"),
            "--audit-log",
            str(tmp_path / "logs" / "audit" / "degradation.jsonl"),
            "--metrics-path",
            str(tmp_path / "metrics" / "degradation_playbook.jsonl"),
            "--validation-playbook",
            str(tmp_path / "docs" / "validation_playbook" / "AC34_degradation.yaml"),
            "--evidence-ledger",
            str(tmp_path / "logs" / "audit" / "evidence.jsonl"),
            "--ops-worklog",
            str(tmp_path / "ops_worklog.jsonl"),
        ],
    )
    assert recover_result.exit_code != 0, recover_result.stdout
