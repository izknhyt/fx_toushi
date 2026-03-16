from __future__ import annotations

from pathlib import Path

import pytest

from tools.evaluate_portfolio_candidates import (
    _parse_required_unique_ids,
    build_evaluation_payload,
    render_summary_md,
)


def test_parse_required_unique_ids_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="baseline_strategies must include at least one id"):
        _parse_required_unique_ids(raw=" , ", field_name="baseline_strategies")


def test_parse_required_unique_ids_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="candidate_strategies contains duplicates: alpha"):
        _parse_required_unique_ids(
            raw="alpha,beta,alpha",
            field_name="candidate_strategies",
        )


def test_build_evaluation_payload_computes_delta_vs_baseline(tmp_path: Path) -> None:
    baseline_payload = {
        "results": [
            {
                "window_name": "2016_2025",
                "summary": {"pf": 1.1, "avg_r": 0.03, "trades": 100, "win_rate": 0.45},
                "acceptance": {"status": "pass"},
                "evidence": {"raw": "baseline_raw.json"},
            }
        ]
    }
    standalone_payloads = {
        "candidate_x": {
            "results": [
                {
                    "window_name": "2016_2025",
                    "summary": {"pf": 1.3, "avg_r": 0.08, "trades": 40, "win_rate": 0.52},
                    "acceptance": {"status": "fail"},
                    "evidence": {"raw": "standalone_raw.json"},
                }
            ]
        }
    }
    combo_payloads = {
        "candidate_x": {
            "results": [
                {
                    "window_name": "2016_2025",
                    "summary": {"pf": 1.18, "avg_r": 0.05, "trades": 120, "win_rate": 0.47},
                    "acceptance": {"status": "pass"},
                    "evidence": {"raw": "combo_raw.json"},
                }
            ]
        }
    }

    payload = build_evaluation_payload(
        baseline_strategy_ids=["alpha", "beta"],
        candidate_strategy_ids=["candidate_x"],
        windows=("2016_2025",),
        baseline_payload=baseline_payload,
        standalone_payloads=standalone_payloads,
        combo_payloads=combo_payloads,
        run_dir=tmp_path,
    )

    candidate = payload["candidates"][0]
    window = candidate["windows"][0]
    assert window["standalone"]["summary"]["pf"] == 1.3
    assert window["combo"]["summary"]["pf"] == 1.18
    assert window["delta_vs_baseline"]["pf"] == 0.08
    assert window["delta_vs_baseline"]["avg_r"] == 0.02
    assert window["delta_vs_baseline"]["trades"] == 20.0


def test_render_summary_md_lists_candidate_rows() -> None:
    payload = {
        "generated_at_utc": "2026-03-16T00:00:00+00:00",
        "baseline_strategy_ids": ["alpha", "beta"],
        "candidate_strategy_ids": ["candidate_x"],
        "selected_windows": ["2016_2025"],
        "candidates": [
            {
                "strategy_id": "candidate_x",
                "windows": [
                    {
                        "window_name": "2016_2025",
                        "standalone": {"summary": {"pf": 1.3, "avg_r": 0.08}},
                        "combo": {"summary": {"pf": 1.18, "avg_r": 0.05}},
                        "delta_vs_baseline": {"pf": 0.08, "avg_r": 0.02},
                    }
                ],
            }
        ],
    }

    rendered = render_summary_md(payload)

    assert "Portfolio Candidate Evaluation" in rendered
    assert "candidate_x" in rendered
    assert "0.08" in rendered
