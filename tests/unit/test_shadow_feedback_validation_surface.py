from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.gui.shadow_feedback_validation_surface import (
    summarize_shadow_feedback_validation_result,
)


def test_summarize_shadow_feedback_validation_result_reads_latest_artifact(tmp_path: Path) -> None:
    output_dir = tmp_path / "reports" / "analysis" / "shadow" / "feedback_validation"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_json = output_dir / "shadow_feedback_validation.json"
    summary_json.write_text(
        json.dumps(
            {
                "generated_at_utc": "2026-03-20T12:30:00+00:00",
                "validation_decision": {
                    "status": "ok",
                    "decision": "adopt",
                    "reasons": ["full_history_improved"],
                    "improved_windows": 2,
                    "degraded_windows": 0,
                    "window_assessments": [
                        {
                            "window_name": "2016_2021",
                            "improved": True,
                            "degraded": False,
                        }
                    ],
                },
                "runtime_guardrail_state": {
                    "status": "active",
                    "decision": "adopt",
                },
                "windows": [
                    {
                        "window_name": "2016_2021",
                        "delta_vs_baseline": {
                            "pf": 0.031,
                            "avg_r": 0.004,
                            "max_drawdown": -0.01,
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = summarize_shadow_feedback_validation_result(
        summary_json_path=summary_json,
        output_dir=output_dir,
    )

    assert payload["status"] == "ok"
    assert payload["decision"] == "adopt"
    assert payload["runtime_guardrail_status"] == "active"
    assert payload["reasons"] == ["full_history_improved"]
    assert payload["window_summary"][0]["window_name"] == "2016_2021"
    assert payload["window_summary"][0]["improved"] is True


def test_summarize_shadow_feedback_validation_result_handles_missing_artifact(tmp_path: Path) -> None:
    payload = summarize_shadow_feedback_validation_result(
        summary_json_path=tmp_path / "missing.json",
        output_dir=tmp_path / "reports" / "analysis" / "shadow" / "feedback_validation",
    )

    assert payload["status"] == "missing"
    assert payload["decision"] == "unknown"
    assert payload["reasons"] == ["validation_artifact_missing"]
