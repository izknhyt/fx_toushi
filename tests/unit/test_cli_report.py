"""Tests for report helpers."""

from __future__ import annotations

from pathlib import Path

from src.interfaces.cli.report import weekly, daily


def test_weekly_writes_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "weekly.md"
    tickets = [
        {
            "id": "t-1",
            "guardrails": {"kill_switch": "none", "spread_status": "normal", "reduce_only": False},
            "board_mode": "normal",
            "risk_summary": {"risk_disclosure": "pending"},
            "audit_refs": {"determinism_hash": "sha256:deadbeef"},
        }
    ]

    payload = weekly(
        profile="m1",
        week="2025-W12",
        tickets=tickets,
        stress_runs=[],
        journal_entries=[],
        journal_path=tmp_path / "journal.jsonl",
        journal_export_dir=tmp_path / "journal",
        returns_path=tmp_path / "returns.csv",
        output_path=output_path,
        dry_run=False,
        kpi={"sharpe": "1.23", "max_dd": "0.05", "win_rate": "0.55", "cum_r": "1.8"},
    )

    assert payload["status"] == "ok"
    assert Path(payload["path"]).exists()
    content = Path(payload["path"]).read_text(encoding="utf-8")
    assert "Ticket Summary" in content
    assert "deadbeef" in content
    assert "1.23" in content
    assert "kpi" in payload


def test_daily_writes_markdown(tmp_path: Path) -> None:
    output_path = tmp_path / "daily.md"
    payload = daily(date="2025-03-21", profile="paper", out=output_path, dry_run=False)

    assert payload["status"] == "ok"
    assert Path(payload["path"]).exists()
    content = Path(payload["path"]).read_text(encoding="utf-8")
    assert "2025-03-21" in content
    assert "paper" in content
