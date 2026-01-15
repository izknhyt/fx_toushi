"""Tests for report helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

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


def _write_reporter_flags(base: Path, *, profile: str, enabled: bool) -> None:
    config_dir = base / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    value = "true" if enabled else "false"
    content = "\n".join(
        [
            'schema_version: "feature_flags.v1"',
            "defaults:",
            f"  {profile}:",
            f"    reporter.enable_extended_blocks: {value}",
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


def test_performance_metric_state_provisional(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_feature_flags(tmp_path, profile="paper", enabled=True)
    returns_path = tmp_path / "returns.parquet"
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=10, freq="D"),
            "return": [0.0] * 10,
        }
    )
    df.to_parquet(returns_path, index=False)

    payload = performance(
        profile="paper",
        output_path=tmp_path / "performance.md",
        metrics_path=tmp_path / "performance.jsonl",
        returns_path=returns_path,
        dry_run=True,
    )

    assert payload["metric_state"] == "provisional"


def test_performance_metric_state_provisional_csv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_feature_flags(tmp_path, profile="paper", enabled=True)
    returns_path = tmp_path / "returns.csv"
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=10, freq="D"),
            "return": [0.0] * 10,
        }
    )
    df.to_csv(returns_path, index=False)

    payload = performance(
        profile="paper",
        output_path=tmp_path / "performance.md",
        metrics_path=tmp_path / "performance.jsonl",
        returns_path=returns_path,
        dry_run=True,
    )

    assert payload["metric_state"] == "provisional"


def test_weekly_extended_blocks_risk_summary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_reporter_flags(tmp_path, profile="m1", enabled=True)
    risk_policy = tmp_path / "config" / "risk_policy.yaml"
    risk_policy.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "profiles:",
                "  m1:",
                "    risk_limits:",
                "      exposure_r_eff_soft_stop: 2.0",
                "      exposure_r_eff_hard_stop: 2.5",
                "    kill_switch:",
                "      drawdown_threshold_pct:",
                "        daily: 2.5",
                "        weekly: 5.0",
                "      capital_floor_pct_of_base: 80",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    logs_dir = tmp_path / "logs" / "events"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "risk.kill_switch.jsonl").write_text(
        '{"ts":"2025-01-01T00:00:00Z","event":"kill_switch.soft_stop","reason":"daily_drawdown"}\n',
        encoding="utf-8",
    )
    (logs_dir / "risk.decision.jsonl").write_text(
        "\n".join(
            [
                '{"event":"risk.decision","ts":"2025-01-01T00:00:00Z",'
                '"decision":{"board_mode":"guarded","kill_switch_state":"soft_stop",'
                '"reduce_only":true,"reason":"daily_drawdown"}}'
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    template_path = tmp_path / "src" / "reporter" / "templates" / "weekly_m1_core_extended.md"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(
        "\n".join(
            [
                "## Risk Summary",
                "- Status: {risk_summary_status}",
                "- Summary: {risk_summary}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "weekly.md"
    payload = weekly(
        profile="m1",
        week="2025-W12",
        tickets=[],
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
    content = output_path.read_text(encoding="utf-8")
    assert "Status: alert" in content
    assert "kill_switch_last=soft_stop" in content
