from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def _write_opt_run(path: Path) -> None:
    payload = {"parameter_stats": {"parameters": {"alpha": {"mean": 0.0, "std": 1.0}}}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "strategies:",
                "  alpha:",
                "    parameters:",
                "      alpha: 3.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_feature_flags(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                'schema_version: "feature_flags.v1"',
                "defaults:",
                "  paper:",
                "    research.parameter_drift: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_research_drift_scan(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    opt_dir = tmp_path / "optimization_runs"
    manifest = tmp_path / "config" / "strategy_manifest.yaml"
    config = tmp_path / "config" / "drift_monitor.yaml"
    metrics_path = tmp_path / "metrics" / "parameter_drift.jsonl"
    event_log = tmp_path / "logs" / "events" / "research_drift.jsonl"
    feature_flags = tmp_path / "config" / "feature_flags.yaml"
    _write_opt_run(opt_dir / "alpha" / "run.json")
    _write_manifest(manifest)
    _write_feature_flags(feature_flags)
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("schema_version: drift_monitor.v1\nthresholds:\n  z_score: 2\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "research",
            "drift",
            "scan",
            "--strategy",
            "alpha",
            "--mode",
            "paper",
            "--profile",
            "paper",
            "--config",
            str(config),
            "--manifest",
            str(manifest),
            "--opt-run-dir",
            str(opt_dir),
            "--metrics-path",
            str(metrics_path),
            "--event-log",
            str(event_log),
            "--health-state-path",
            str(tmp_path / "snapshots" / "latest" / "health_state.json"),
            "--feature-flags",
            str(feature_flags),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "degraded"
    assert Path(payload["health_state_path"]).exists()
