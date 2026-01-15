from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app
from src.ops.postmortem import IncidentPostmortemService
from src.ops.trade_forensics import TradeForensicsAnalyzer


def test_ops_incident_cli_flow(tmp_path: Path, monkeypatch) -> None:
    template_path = tmp_path / "docs" / "templates" / "postmortem.md"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text("# Postmortem {{incident_id}}\n", encoding="utf-8")

    service = IncidentPostmortemService(
        report_dir=tmp_path / "reports" / "ops" / "incidents",
        log_path=tmp_path / "logs" / "ops" / "incidents.jsonl",
        template_path=template_path,
        audit_dir=tmp_path / "logs" / "audit",
    )
    analyzer = TradeForensicsAnalyzer(
        postmortem_service=service,
        report_dir=tmp_path / "reports" / "ops" / "incidents",
    )

    monkeypatch.setattr("src.interfaces.cli.ops_incident.IncidentPostmortemService", lambda: service)
    monkeypatch.setattr("src.interfaces.cli.ops_incident.TradeForensicsAnalyzer", lambda: analyzer)

    app = create_cli_app()
    runner = CliRunner()

    open_result = runner.invoke(
        app,
        [
            "ops",
            "incident",
            "open",
            "--category",
            "data",
            "--severity",
            "critical",
            "--json",
        ],
    )
    assert open_result.exit_code == 0, open_result.stdout
    payload = json.loads(open_result.stdout)
    incident_id = payload["incident_id"]

    timeline_result = runner.invoke(
        app,
        [
            "ops",
            "incident",
            "timeline-add",
            "--incident",
            incident_id,
            "--runbook",
            "RUN-DATA-05#1",
            "--note",
            "manual csv",
            "--json",
        ],
    )
    assert timeline_result.exit_code == 0, timeline_result.stdout

    forensics_result = runner.invoke(
        app,
        [
            "ops",
            "incident",
            "forensics",
            "--incident",
            incident_id,
            "--window",
            "6h",
            "--report",
            "--json",
        ],
    )
    assert forensics_result.exit_code == 0, forensics_result.stdout
    forensics_payload = json.loads(forensics_result.stdout)
    assert forensics_payload["reports"]

    close_result = runner.invoke(
        app,
        [
            "ops",
            "incident",
            "close",
            "--incident",
            incident_id,
            "--verification-note",
            "verified",
            "--verified-by",
            "ops",
            "--json",
        ],
    )
    assert close_result.exit_code == 0, close_result.stdout
