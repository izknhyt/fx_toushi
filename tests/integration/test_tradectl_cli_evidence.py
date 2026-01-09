"""Integration coverage for tradectl evidence-generating commands."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from src.interfaces.cli import create_cli_app
from typer.testing import CliRunner


def _fixed_time() -> datetime:
    return datetime(2025, 3, 21, 2, 1, 30, tzinfo=timezone.utc)


def test_execution_recalibrate_generates_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    app = create_cli_app()

    monkeypatch.setattr("src.interfaces.cli.execution._current_time", _fixed_time)

    with runner.isolated_filesystem():
        source = Path("reports/performance/live_fill_stats.parquet")
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("timestamp,latency,slippage\n", encoding="utf-8")
        output_path = Path("config/execution_model.calib.yaml")

        result = runner.invoke(
            app,
            [
                "execution",
                "recalibrate",
                "--from",
                str(source),
                "--window",
                "14d",
                "--out",
                str(output_path),
            ],
        )
        assert result.exit_code == 0, result.output
        assert output_path.exists()

        document = yaml.safe_load(output_path.read_text(encoding="utf-8"))
        assert document["metadata"]["generated_at"] == _fixed_time().isoformat()
        assert document["metadata"]["source"] == str(source)
        assert document["calibration"]["sample_count"] == 240
        assert (
            "Mock calibration generated for audit scaffolding."
            in document["calibration"]["notes"][0]
        )


def test_scoring_diagnostics_emits_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    app = create_cli_app()

    monkeypatch.setattr("src.interfaces.cli.scoring._current_time", _fixed_time)

    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            [
                "scoring",
                "diagnostics",
                "--strategy",
                "m1_baseline_ma_rsi",
                "--window",
                "4w",
            ],
        )
        assert result.exit_code == 0, result.output

        report_path = Path("reports/diagnostics/scoring_2025-03-21.md")
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "# Scoring Diagnostics - m1_baseline_ma_rsi" in content
        assert "Generated At: 2025-03-21T02:01:30+00:00" in content
        assert "Portfolio Drift Ratio: 0.940" in content


def test_kill_switch_review_records_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    app = create_cli_app()

    monkeypatch.setattr("src.interfaces.cli.kill_switch._current_time", _fixed_time)

    with runner.isolated_filesystem():
        attachment = Path("reports/diagnostics/scoring_mock.md")
        attachment.parent.mkdir(parents=True, exist_ok=True)
        attachment.write_text("placeholder", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "kill-switch",
                "review",
                "--reason",
                "execution_latency",
                "--strategy",
                "m1_baseline_ma_rsi",
                "--mode",
                "live",
                "--recommend",
                "resume",
                "--attach",
                str(attachment),
            ],
        )
        assert result.exit_code == 0, result.output

        evidence_path = Path("reports/audit/kill_switch_review/20250321T020130Z.md")
        assert evidence_path.exists()
        content = evidence_path.read_text(encoding="utf-8")
        assert "- Generated At: 2025-03-21T02:01:30+00:00" in content
        assert "- Recommendation: resume" in content
        assert f"- {attachment}" in content


def test_kill_switch_resume_requires_attachments(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    app = create_cli_app()

    monkeypatch.setattr("src.interfaces.cli.kill_switch._current_time", _fixed_time)

    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            [
                "kill-switch",
                "review",
                "--reason",
                "data_gap",
                "--mode",
                "paper",
                "--recommend",
                "resume",
            ],
        )
        assert result.exit_code == 43
        assert "Evidence attachments are required" in result.output
