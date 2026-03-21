from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.gui.multi_pair_preparation_surface import (
    summarize_multi_pair_preparation_result,
)


def test_summarize_multi_pair_preparation_result_returns_missing_when_no_artifacts(tmp_path: Path) -> None:
    summary = summarize_multi_pair_preparation_result(output_dir=tmp_path / "shadow")

    assert summary["status"] == "missing"
    assert summary["recommended_action"] == "run_multi_pair_preparation"
    assert summary["step_counts"] == {"completed": 0, "pending": 0, "blocked": 0}


def test_summarize_multi_pair_preparation_result_reads_latest_payload_and_snapshots(tmp_path: Path) -> None:
    output_dir = tmp_path / "shadow"
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_validation = output_dir / "shadow_multi_pair_eurusd_baseline_validation.json"
    baseline_validation.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "window_name": "2016_2025",
                        "summary": {"pf": 1.2, "avg_r": 0.03, "max_drawdown": 0.10},
                        "acceptance": {"status": "pass"},
                    },
                    {
                        "window_name": "2022_2025",
                        "summary": {"pf": 1.25, "avg_r": 0.05, "max_drawdown": 0.08},
                        "acceptance": {"status": "pass"},
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    multi_validation = output_dir / "shadow_multi_pair_eurusd_validation.json"
    multi_validation.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "window_name": "2016_2025",
                        "summary": {"pf": 1.22, "avg_r": 0.031, "max_drawdown": 0.11},
                        "acceptance": {"status": "pass"},
                    },
                    {
                        "window_name": "2022_2025",
                        "summary": {"pf": 1.28, "avg_r": 0.051, "max_drawdown": 0.085},
                        "acceptance": {"status": "pass"},
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    candidates_snapshot = output_dir / "portfolio_candidates_snapshot.json"
    candidates_snapshot.write_text(
        json.dumps(
            {
                "symbols": ["EURUSD"],
                "candidates": [{"strategy_id": "alpha"}, {"strategy_id": "beta"}],
                "admission_outcomes": [{"status": "accept"}, {"status": "reject"}],
                "selected_strategy_ids": ["alpha", "beta"],
                "warnings": ["missing secondary feature"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    admit_snapshot = output_dir / "portfolio_admit_snapshot.json"
    admit_snapshot.write_text(
        json.dumps(
            {
                "symbols": ["EURUSD"],
                "candidates": [{"strategy_id": "alpha"}],
                "admission_outcomes": [{"status": "accept"}, {"status": "defer"}, {"status": "reject"}],
                "selected_strategy_ids": ["alpha"],
                "warnings": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    latest_path = output_dir / "shadow_multi_pair_preparation_20260321T000000Z.json"
    latest_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "packet": {
                    "phase": "multi_pair_preparation",
                    "status": "ready",
                    "execution_status": "completed",
                    "next_symbol": "EURUSD",
                    "windows": ["2016_2025", "2022_2025"],
                    "required_inputs": [],
                    "runbook_ref": "docs/runbooks/PORTFOLIO-MULTIPAIR-01.md",
                    "runner_command": "tradectl portfolio next-stage --phase multi_pair_preparation --run",
                    "commands": [
                        {"step": "kernel_validation", "command": "python3 validate.py", "artifacts": ["validation.json"]},
                        {"step": "candidate_snapshot", "command": "tradectl portfolio candidates", "artifacts": [str(candidates_snapshot)]},
                        {"step": "admission_snapshot", "command": "tradectl portfolio admit", "artifacts": [str(admit_snapshot)]},
                    ],
                    "execution_steps": [
                        {"step": "kernel_validation", "status": "completed", "command": "python3 validate.py", "artifacts": ["validation.json"]},
                        {"step": "candidate_snapshot", "status": "completed", "command": "tradectl portfolio candidates", "artifacts": [str(candidates_snapshot)]},
                    ],
                    "artifacts": {
                        "baseline_validation_summary_json": str(baseline_validation),
                        "validation_summary_json": str(multi_validation),
                        "candidates_snapshot_json": str(candidates_snapshot),
                        "admit_snapshot_json": str(admit_snapshot),
                    },
                },
                "json_path": str(latest_path),
                "markdown_path": str(output_dir / "shadow_multi_pair_preparation_20260321T000000Z.md"),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = summarize_multi_pair_preparation_result(output_dir=output_dir)

    assert summary["status"] == "ok"
    assert summary["recommended_action"] == "review_multi_pair_shadow_pilot_promotion"
    assert summary["step_counts"] == {"completed": 2, "pending": 1, "blocked": 0}
    assert summary["latest"]["next_symbol"] == "EURUSD"
    assert summary["latest"]["packet_status"] == "ready"
    assert summary["latest"]["execution_status"] == "completed"
    assert summary["latest"]["decision_summary"]["decision_status"] == "promote_shadow_pilot"
    assert summary["latest"]["candidate_snapshot_summary"]["candidate_count"] == 2
    assert summary["latest"]["candidate_snapshot_summary"]["selected_strategy_count"] == 2
    assert summary["latest"]["admit_snapshot_summary"]["admission_summary"] == {
        "accept": 1,
        "defer": 1,
        "reject": 1,
    }
    assert summary["recent"][0]["step"] == "kernel_validation"
    assert summary["recent"][2]["status"] == "pending"
