from __future__ import annotations

from pathlib import Path

from src.ops.dashboard import OpsHealthDashboardService


def test_ops_dashboard_handles_missing_inputs(tmp_path: Path) -> None:
    service = OpsHealthDashboardService(
        health_state_path=tmp_path / "health_state.json",
        kill_switch_state_path=tmp_path / "kill_switch_state.json",
        gate_state_path=tmp_path / "gate_state.json",
        benchmark_gap_log=tmp_path / "benchmark_gap.jsonl",
        metrics_path=tmp_path / "metrics.jsonl",
        journal_path=tmp_path / "journal.jsonl",
    )
    payload = service.build().to_dict()
    assert payload["status"] == "degraded"
    assert "health_state_missing" in payload["diagnostics"]
