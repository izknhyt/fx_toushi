"""Integration coverage focused on scoring diagnostics evidence generation."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from src.interfaces.cli.scoring import run_diagnostics


@pytest.fixture
def fixed_time() -> datetime:
    return datetime(2025, 3, 21, 2, 1, 30, tzinfo=timezone.utc)


def test_run_diagnostics_generates_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixed_time: datetime
) -> None:
    """Baseline strategy should produce Live Guard-aligned markdown evidence."""

    monkeypatch.setattr("src.interfaces.cli.scoring._current_time", lambda: fixed_time)
    monkeypatch.chdir(tmp_path)

    payload = run_diagnostics(strategy="m1_baseline_ma_rsi", window="4w", fmt="md")
    relative_path = Path("reports/diagnostics/scoring_2025-03-21.md")
    report_path = tmp_path / relative_path

    assert payload["status"] == "ok"
    assert payload["output"] == str(relative_path)
    assert payload["generated_at"] == fixed_time.isoformat()
    assert payload["action_required"] is False

    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "# Scoring Diagnostics - m1_baseline_ma_rsi" in content
    assert "Generated At: 2025-03-21T02:01:30+00:00" in content
    assert "Portfolio Drift Ratio: 0.940" in content
    assert "Mock report for audit scaffolding." in content


def test_run_diagnostics_flags_portfolio_drift_breach(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixed_time: datetime
) -> None:
    """Out-of-band PF drift should force action-required JSON evidence."""

    breach_time = fixed_time + timedelta(days=7)
    monkeypatch.setattr("src.interfaces.cli.scoring._current_time", lambda: breach_time)
    monkeypatch.chdir(tmp_path)

    output_dir = Path("reports/custom_diagnostics")
    payload = run_diagnostics(
        strategy="intraday_scalper_alpha",
        window="2w",
        output=output_dir,
        fmt="json",
    )

    relative_path = Path("reports/custom_diagnostics/scoring_2025-03-28.json")
    report_path = tmp_path / relative_path

    assert payload["status"] == "ok"
    assert payload["output"] == str(relative_path)
    assert payload["generated_at"] == breach_time.isoformat()
    assert payload["action_required"] is True

    assert report_path.exists()
    document = json.loads(report_path.read_text(encoding="utf-8"))
    assert document["action_required"] is True
    assert pytest.approx(document["analysis"]["portfolio_drift"], rel=1e-6) == 1.18
    assert document["analysis"]["spread_penalty"] == pytest.approx(0.27)
    assert document["analysis"]["reject_reasons"] == [
        "insufficient_watchlist_alpha",
        "spread_guard_trip",
        "latency_window_exceeded",
    ]
    assert "Mock report for audit scaffolding." in document["notes"][0]
