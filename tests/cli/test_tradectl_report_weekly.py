from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app
from src.interfaces.cli import tickets as tickets_actions


def test_report_weekly_renders_ticket_summary(monkeypatch: "MonkeyPatch", tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    # prepare ticket store with one pending disclosure
    store_path = tmp_path / "tickets.jsonl"
    store_path.write_text(
        json.dumps(
            {
                "ticket_id": "T1",
                "guardrails": {"kill_switch": "soft_stop", "spread_status": "cooldown", "reduce_only": True},
                "board_mode": "guarded",
                "risk_summary": {"risk_disclosure": "pending"},
                "audit_refs": {"determinism_hash": "deadbeef"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tickets_actions, "TICKET_STORE_PATH", store_path)
    out_path = tmp_path / "weekly.md"
    result = runner.invoke(
        app,
        [
            "report",
            "weekly",
            "--out",
            str(out_path),
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "ticket_summary" in payload
    assert out_path.exists()
