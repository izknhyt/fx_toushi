"""Tests for report helpers."""

from __future__ import annotations

from pathlib import Path

from src.interfaces.cli.report import daily, performance, weekly


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


def _write_feature_flags(base: Path, *, profile: str, enabled: bool) -> None:
    config_dir = base / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    value = "true" if enabled else "false"
    content = "\n".join(
        [
            'schema_version: "feature_flags.v1"',
            "defaults:",
            f"  {profile}:",
            f"    reports.performance.enable: {value}",
        ]
    )
    (config_dir / "feature_flags.yaml").write_text(content + "\n", encoding="utf-8")


def test_performance_disabled_when_flag_off(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_feature_flags(tmp_path, profile="paper", enabled=False)
    output_path = tmp_path / "performance.md"
    metrics_path = tmp_path / "performance.jsonl"

    payload = performance(
        profile="paper",
        output_path=output_path,
        metrics_path=metrics_path,
        kpi={"sharpe": 1.0, "max_dd": 0.1, "win_rate": 0.5, "cum_r": 1.2},
    )

    assert payload["status"] == "disabled"
    assert not output_path.exists()
    assert not metrics_path.exists()


def test_performance_enabled_writes_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_feature_flags(tmp_path, profile="paper", enabled=True)
    output_path = tmp_path / "performance.md"
    metrics_path = tmp_path / "performance.jsonl"

    payload = performance(
        profile="paper",
        output_path=output_path,
        metrics_path=metrics_path,
        kpi={"sharpe": 1.0, "max_dd": 0.1, "win_rate": 0.5, "cum_r": 1.2},
        dry_run=False,
    )

    assert payload["status"] == "ok"
    assert output_path.exists()
    assert metrics_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "Performance Snapshot" in content
