from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def test_portfolio_evaluate_cli_wraps_tool(monkeypatch, tmp_path: Path) -> None:
    def _fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        output_json = Path(cmd[cmd.index("--output-json") + 1])
        output_md = Path(cmd[cmd.index("--output-md") + 1])
        payload = {
            "generated_at_utc": "2026-03-16T13:00:00+00:00",
            "baseline_strategy_ids": ["m1_asia_compression_expansion_breakout"],
            "candidate_strategy_ids": ["m1_baseline_donchian_upper_only"],
            "selected_windows": ["2016_2025", "2016_2021"],
            "candidates": [],
        }
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        output_md.write_text("# stub\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    app = create_cli_app()
    runner = CliRunner()
    data_path = tmp_path / "data.parquet"
    data_path.write_text("stub", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "portfolio",
            "evaluate",
            "--baseline-strategies",
            "m1_asia_compression_expansion_breakout",
            "--candidate-strategies",
            "m1_baseline_donchian_upper_only",
            "--data-path",
            str(data_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["command"] == "evaluate"
    assert payload["summary_json"].endswith("portfolio_candidate_evaluation.json")
    assert payload["result"]["baseline_strategy_ids"] == ["m1_asia_compression_expansion_breakout"]


def test_portfolio_review_cli_wraps_tool(monkeypatch, tmp_path: Path) -> None:
    def _fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        output_json = Path(cmd[cmd.index("--output-json") + 1])
        output_md = Path(cmd[cmd.index("--output-md") + 1])
        payload = {
            "generated_at_utc": "2026-03-16T13:05:00+00:00",
            "windows": [{"window_name": "2016_2025"}],
            "persistent_strategy_drags": [],
        }
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        output_md.write_text("# review\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    app = create_cli_app()
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "portfolio",
            "review",
            "--run-stamp",
            "20260315T132308Z",
            "--output-dir",
            str(tmp_path / "out"),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["command"] == "review"
    assert payload["summary_md"].endswith("portfolio_validation_review.md")
    assert payload["result"]["windows"][0]["window_name"] == "2016_2025"


def test_portfolio_candidates_cli_wraps_snapshot_tool(monkeypatch, tmp_path: Path) -> None:
    def _fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        output_json = Path(cmd[cmd.index("--output") + 1])
        payload = {
            "generated_at": "2026-03-16T13:10:00Z",
            "symbols": ["USDJPY"],
            "candidates": [{"candidate_id": "abc", "strategy_id": "alpha"}],
            "admission_outcomes": [{"strategy_id": "alpha", "decision": "accept"}],
            "selected_strategy_ids": ["alpha"],
            "warnings": [],
        }
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    app = create_cli_app()
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "portfolio",
            "candidates",
            "--symbols",
            "USDJPY",
            "--output-dir",
            str(tmp_path / "out"),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["command"] == "candidates"
    assert payload["result"]["candidates"][0]["candidate_id"] == "abc"


def test_portfolio_admit_cli_wraps_snapshot_tool(monkeypatch, tmp_path: Path) -> None:
    def _fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        output_json = Path(cmd[cmd.index("--output") + 1])
        payload = {
            "generated_at": "2026-03-16T13:11:00Z",
            "symbols": ["USDJPY"],
            "candidates": [{"candidate_id": "abc", "strategy_id": "alpha"}],
            "admission_outcomes": [{"strategy_id": "alpha", "decision": "accept"}],
            "selected_strategy_ids": ["alpha"],
            "warnings": [],
        }
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    app = create_cli_app()
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "portfolio",
            "admit",
            "--symbols",
            "USDJPY",
            "--output-dir",
            str(tmp_path / "out"),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["command"] == "admit"
    assert payload["result"]["selected_strategy_ids"] == ["alpha"]
    assert payload["result"]["admission_outcomes"][0]["decision"] == "accept"


def test_portfolio_next_stage_cli_wraps_tool(monkeypatch, tmp_path: Path) -> None:
    def _fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        output_dir = Path(cmd[cmd.index("--output-dir") + 1])
        output_prefix = cmd[cmd.index("--output-prefix") + 1]
        output_json = output_dir / f"{output_prefix}.json"
        output_md = output_dir / f"{output_prefix}.md"
        payload = {
            "status": "ok",
            "packet": {
                "phase": "candidate_onboarding",
                "status": "ready",
                "runbook_ref": "docs/runbooks/PORTFOLIO-CANDIDATE-01.md",
            },
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        output_md.write_text("# next-stage\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    app = create_cli_app()
    runner = CliRunner()
    data_path = tmp_path / "data.parquet"
    data_path.write_text("stub", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "portfolio",
            "next-stage",
            "--phase",
            "candidate_onboarding",
            "--candidate-strategies",
            "alpha_candidate",
            "--data-path",
            str(data_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["command"] == "next-stage"
    assert payload["summary_json"].endswith("shadow_next_stage.json")
    assert payload["result"]["packet"]["phase"] == "candidate_onboarding"
