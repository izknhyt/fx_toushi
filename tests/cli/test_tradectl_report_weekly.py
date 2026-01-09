from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch
from src.interfaces.cli import create_cli_app, tickets as tickets_actions
from typer.testing import CliRunner


def test_report_weekly_renders_ticket_summary(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    # prepare ticket store with one pending disclosure
    store_path = tmp_path / "tickets.jsonl"
    store_path.write_text(
        json.dumps(
            {
                "ticket_id": "T1",
                "guardrails": {
                    "kill_switch": "soft_stop",
                    "spread_status": "cooldown",
                    "reduce_only": True,
                },
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
    stress_dir = tmp_path / "reports" / "stress"
    stress_dir.mkdir(parents=True, exist_ok=True)
    (stress_dir / "brexit_report.md").write_text(
        "# Stress Test Report: brexit\nresult: ok\n", encoding="utf-8"
    )
    journal_path = tmp_path / "logs" / "journal" / "entries.jsonl"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(
        json.dumps(
            {
                "ts": "2025-03-20T12:00:00Z",
                "ticket_id": "T1",
                "user": "alice",
                "note": "approved",
                "week": "2025-W12",
            }
        ),
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "report",
            "weekly",
            "--out",
            str(out_path),
            "--stress-dir",
            str(stress_dir),
            "--journal-path",
            str(journal_path),
            "--week",
            "2025-W12",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "ticket_summary" in payload
    assert out_path.exists()
    assert payload["week"] == "2025-W12"
    assert payload["stress_runs"][0]["scenario"] == "brexit"
    assert payload["journal_entries"][0]["ticket_id"] == "T1"
    assert payload["journal_export"].endswith("reports/journal/2025-W12.md")
