from __future__ import annotations

import json
from pathlib import Path

from src.research.drift import ParameterDriftMonitor


def _write_opt_run(path: Path, *, stats: dict[str, dict[str, float]]) -> None:
    payload = {"parameter_stats": stats}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_manifest(path: Path, *, params: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "strategies:",
                "  alpha:",
                "    parameters:",
                *[
                    f"      {name}: {value}"
                    for name, value in params.items()
                ],
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_parameter_drift_monitor_detects_degraded(tmp_path: Path) -> None:
    opt_dir = tmp_path / "optimization_runs"
    manifest = tmp_path / "config" / "strategy_manifest.yaml"
    config = tmp_path / "config" / "drift_monitor.yaml"
    metrics_path = tmp_path / "metrics" / "parameter_drift.jsonl"
    event_log = tmp_path / "logs" / "events" / "research_drift.jsonl"
    _write_opt_run(
        opt_dir / "alpha" / "run.json",
        stats={"parameters": {"alpha": {"mean": 0.0, "std": 1.0}}},
    )
    _write_manifest(manifest, params={"alpha": 3.0})
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("schema_version: drift_monitor.v1\nthresholds:\n  z_score: 2\n", encoding="utf-8")

    monitor = ParameterDriftMonitor(
        config_path=config,
        manifest_path=manifest,
        opt_run_dir=opt_dir,
        metrics_path=metrics_path,
        event_log=event_log,
    )
    alert = monitor.scan(strategy_id="alpha", mode="paper")

    assert alert.status == "degraded"
    assert metrics_path.exists()
    assert event_log.exists()


def test_parameter_drift_monitor_missing_inputs(tmp_path: Path) -> None:
    monitor = ParameterDriftMonitor(
        config_path=tmp_path / "config" / "drift_monitor.yaml",
        manifest_path=tmp_path / "config" / "strategy_manifest.yaml",
        opt_run_dir=tmp_path / "optimization_runs",
        metrics_path=tmp_path / "metrics" / "parameter_drift.jsonl",
        event_log=tmp_path / "logs" / "events" / "research_drift.jsonl",
    )
    alert = monitor.scan(strategy_id="alpha", mode="paper")

    assert alert.status == "missing"
