from __future__ import annotations

import json
from pathlib import Path

from tools.review_long_horizon_validation import (
    _summary_from_run_stamp,
    build_review,
    render_review_md,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_build_review_ranks_strategy_direction_and_year_drags(tmp_path: Path) -> None:
    raw_path = tmp_path / "validation_log" / "window_fail.json"
    report_json_path = tmp_path / "analysis" / "window_fail_report.json"
    report_md_path = tmp_path / "analysis" / "window_fail_report.md"
    _write_json(
        raw_path,
        {
            "trades": [
                {
                    "strategy_id": "bad_breakout",
                    "opened_at": "2019-01-03T00:00:00+00:00",
                    "direction": "short",
                    "r_multiple": -1.0,
                    "pnl": -100.0,
                },
                {
                    "strategy_id": "bad_breakout",
                    "opened_at": "2019-02-03T00:00:00+00:00",
                    "direction": "short",
                    "r_multiple": -0.8,
                    "pnl": -80.0,
                },
                {
                    "strategy_id": "bad_breakout",
                    "opened_at": "2020-01-03T00:00:00+00:00",
                    "direction": "short",
                    "r_multiple": -0.6,
                    "pnl": -60.0,
                },
                {
                    "strategy_id": "bad_breakout",
                    "opened_at": "2020-02-03T00:00:00+00:00",
                    "direction": "short",
                    "r_multiple": -0.4,
                    "pnl": -40.0,
                },
                {
                    "strategy_id": "bad_breakout",
                    "opened_at": "2020-03-03T00:00:00+00:00",
                    "direction": "short",
                    "r_multiple": -0.2,
                    "pnl": -20.0,
                },
                {
                    "strategy_id": "bad_breakout",
                    "opened_at": "2020-04-03T00:00:00+00:00",
                    "direction": "long",
                    "r_multiple": 0.5,
                    "pnl": 50.0,
                },
                {
                    "strategy_id": "good_pullback",
                    "opened_at": "2020-05-03T00:00:00+00:00",
                    "direction": "long",
                    "r_multiple": 0.7,
                    "pnl": 70.0,
                },
            ]
        },
    )
    _write_json(
        report_json_path,
        {
            "summary": {"pf": 0.98, "avg_r": -0.1, "count": 7},
            "acceptance_gate": {"status": "fail", "checks": {"avg_r_positive": False}},
            "weak_points": [{"scope": "year", "key": "2019", "avg_r": -0.9}],
            "next_actions": ["Split strategy by regime/session and disable weak regime buckets."],
        },
    )
    report_md_path.write_text("# report\n", encoding="utf-8")
    summary_payload = {
        "_source_path": str(tmp_path / "summary.json"),
        "results": [
            {
                "window_name": "2016_2021",
                "purpose": "pre_recent_regimes",
                "summary": {"pf": 0.98, "avg_r": -0.1, "max_drawdown": 0.2, "trades": 7},
                "acceptance": {"status": "fail", "checks": {"avg_r_positive": False}},
                "evidence": {
                    "raw": str(raw_path),
                    "report_json": str(report_json_path),
                    "report_md": str(report_md_path),
                },
            }
        ],
    }

    review = build_review(summary_payload, top_n=3)

    assert review["window_count"] == 1
    window = review["windows"][0]
    assert window["top_strategy_drags"][0]["strategy_id"] == "bad_breakout"
    assert window["top_direction_drags"][0]["direction"] == "short"
    assert window["top_strategy_year_drags"][0]["year"] == "2019"
    assert any("Gate or de-prioritize `bad_breakout`" in item for item in window["recommendations"])
    assert any("directional gating" in item for item in window["recommendations"])
    assert review["persistent_strategy_drags"][0]["strategy_id"] == "bad_breakout"

    rendered = render_review_md(review)
    assert "Long-Horizon Validation Review" in rendered
    assert "bad_breakout" in rendered
    assert "2016_2021" in rendered


def test_build_review_skips_passing_windows_by_default(tmp_path: Path) -> None:
    raw_path = tmp_path / "validation_log" / "window_pass.json"
    report_json_path = tmp_path / "analysis" / "window_pass_report.json"
    report_md_path = tmp_path / "analysis" / "window_pass_report.md"
    _write_json(
        raw_path,
        {
            "trades": [
                {
                    "strategy_id": "good_pullback",
                    "opened_at": "2024-01-03T00:00:00+00:00",
                    "direction": "long",
                    "r_multiple": 0.7,
                    "pnl": 70.0,
                }
            ]
        },
    )
    _write_json(
        report_json_path,
        {
            "summary": {"pf": 1.2, "avg_r": 0.7, "count": 1},
            "acceptance_gate": {"status": "pass", "checks": {"avg_r_positive": True}},
            "weak_points": [],
            "next_actions": [],
        },
    )
    report_md_path.write_text("# report\n", encoding="utf-8")
    summary_payload = {
        "_source_path": str(tmp_path / "summary.json"),
        "results": [
            {
                "window_name": "2022_2025",
                "purpose": "recent_regimes",
                "summary": {"pf": 1.2, "avg_r": 0.7, "max_drawdown": 0.02, "trades": 1},
                "acceptance": {"status": "pass", "checks": {"avg_r_positive": True}},
                "evidence": {
                    "raw": str(raw_path),
                    "report_json": str(report_json_path),
                    "report_md": str(report_md_path),
                },
            }
        ],
    }

    review = build_review(summary_payload)

    assert review["window_count"] == 0
    assert review["windows"] == []
    assert review["persistent_strategy_drags"] == []


def test_summary_from_run_stamp_reconstructs_results(tmp_path: Path) -> None:
    validation_dir = tmp_path / "validation_log"
    analysis_dir = tmp_path / "analysis"
    raw_path = validation_dir / "long_horizon_portfolio_20260315T132308Z_2016_2021.json"
    report_json_path = analysis_dir / "long_horizon_portfolio_20260315T132308Z_2016_2021_report.json"
    report_md_path = analysis_dir / "long_horizon_portfolio_20260315T132308Z_2016_2021_report.md"

    _write_json(raw_path, {"trades": []})
    _write_json(
        report_json_path,
        {
            "metrics": {"max_drawdown": 0.12},
            "summary": {"pf": 1.08, "avg_r": 0.01, "count": 423, "win_rate": 0.44},
            "acceptance_gate": {"status": "fail", "checks": {"pf_min_1_10": False}},
        },
    )
    report_md_path.write_text("# report\n", encoding="utf-8")

    summary = _summary_from_run_stamp(
        run_stamp="20260315T132308Z",
        validation_log_dir=validation_dir,
        analysis_dir=analysis_dir,
    )

    assert summary["_source_path"] == "run_stamp:20260315T132308Z"
    assert len(summary["results"]) == 1
    row = summary["results"][0]
    assert row["window_name"] == "2016_2021"
    assert row["summary"]["pf"] == 1.08
    assert row["summary"]["max_drawdown"] == 0.12
    assert row["acceptance"]["status"] == "fail"
    assert row["evidence"]["raw"] == str(raw_path)
