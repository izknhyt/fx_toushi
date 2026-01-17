from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pytest import MonkeyPatch
from src.interfaces.cli import create_cli_app, tickets as tickets_actions
from src.journal import JournalEntry, TradeJournalService
from typer.testing import CliRunner


def test_report_weekly_renders_ticket_summary(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "feature_flags.yaml").write_text(
        "\n".join(
            [
                'schema_version: "feature_flags.v1"',
                "defaults:",
                "  m1:",
                "    journal.enabled: true",
                "    journal.weekly_summary: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
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
    journal_path = tmp_path / "logs" / "journal" / "journal_entries.db"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_service = TradeJournalService(
        path=journal_path,
        metrics_path=tmp_path / "journal_metrics.jsonl",
        audit_log_path=tmp_path / "journal_audit.jsonl",
    )
    journal_service.append(
        JournalEntry(
            ts=datetime(2025, 3, 20, 12, 0, tzinfo=timezone.utc),
            ticket_id="T1",
            user="alice",
            note="approved",
        )
    )
    template_path = tmp_path / "src" / "reporter" / "templates" / "weekly_m1_core.md"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(
        "\n".join(
            [
                "# Weekly Report",
                "## Ticket Summary",
                "{tickets_overview}",
                "{determinism_hashes}",
                "## Stress Runs",
                "{stress_runs}",
                "## Trade Journal",
                "{trade_journal}",
            ]
        )
        + "\n",
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
            "--template",
            str(template_path),
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
