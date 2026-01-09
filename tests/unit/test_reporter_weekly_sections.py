from __future__ import annotations

from pathlib import Path

from src.reporter.generator import ReportGenerator


def test_weekly_report_includes_stress_and_journal(tmp_path: Path) -> None:
    template = tmp_path / "weekly.md"
    template.write_text(
        "## Ticket Summary\n"
        "- mode={board_mode}\n"
        "- guardrails={guardrails.kill_switch}/{guardrails.spread_status}/"
        "{guardrails.reduce_only}\n"
        "## Stress Runs\n"
        "{stress_runs}\n"
        "## Trade Journal\n"
        "{trade_journal}\n",
        encoding="utf-8",
    )

    tickets = [
        {
            "guardrails": {
                "kill_switch": "guarded",
                "spread_status": "cooldown",
                "reduce_only": True,
            },
            "board_mode": "guarded",
            "risk_summary": {"risk_disclosure": "pending"},
            "audit_refs": {"determinism_hash": "deadbeef"},
        }
    ]
    stress_runs = [
        {
            "scenario": "brexit",
            "status": "ok",
            "summary": "vol spike contained",
            "artifacts": ["reports/stress/brexit_report.md"],
        }
    ]
    journal_entries = [
        {"ts": "2025-03-20T12:00:00Z", "ticket_id": "T1", "user": "alice", "note": "approved"}
    ]

    text = ReportGenerator().render_weekly_report(
        week="2025-W12",
        tickets=tickets,
        stress_runs=stress_runs,
        journal_entries=journal_entries,
        template_path=template,
    )

    assert "mode=guarded" in text
    assert "brexit" in text
    assert "reports/stress/brexit_report.md" in text
    assert "T1" in text and "alice" in text


def test_weekly_report_falls_back_to_default_template(tmp_path: Path) -> None:
    text = ReportGenerator().render_weekly_report(
        week="2025-W13",
        tickets=[],
        stress_runs=[],
        journal_entries=[],
        template_path=Path("src/reporter/templates/weekly_default.md"),
    )
    assert "No stress runs" in text
    assert "No entries" in text
