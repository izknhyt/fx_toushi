from __future__ import annotations

from pathlib import Path

from tools.run_allocator_tuning_review import build_summary_payload, render_summary_md


def test_build_summary_payload_computes_delta_vs_baseline(tmp_path: Path) -> None:
    baseline_payload = {
        "results": [
            {
                "window_name": "2016_2021",
                "summary": {"pf": 1.0, "avg_r": 0.01, "trades": 100, "win_rate": 0.45, "max_drawdown": 0.10},
                "acceptance": {"status": "fail"},
                "evidence": {"raw": "baseline_2016_2021.json"},
            },
            {
                "window_name": "2016_2025",
                "summary": {"pf": 1.1, "avg_r": 0.03, "trades": 160, "win_rate": 0.46, "max_drawdown": 0.12},
                "acceptance": {"status": "pass"},
                "evidence": {"raw": "baseline_2016_2025.json"},
            },
        ]
    }
    case_payloads = {
        "demote_alpha_role_priority": {
            "results": [
                {
                    "window_name": "2016_2021",
                    "summary": {"pf": 1.05, "avg_r": 0.02, "trades": 104, "win_rate": 0.47, "max_drawdown": 0.09},
                    "acceptance": {"status": "pass"},
                    "evidence": {"raw": "case_2016_2021.json"},
                },
                {
                    "window_name": "2016_2025",
                    "summary": {"pf": 1.12, "avg_r": 0.04, "trades": 162, "win_rate": 0.47, "max_drawdown": 0.11},
                    "acceptance": {"status": "pass"},
                    "evidence": {"raw": "case_2016_2025.json"},
                },
            ]
        }
    }
    generated_cases = [
        {
            "case_id": "demote_alpha_role_priority",
            "note": "Demote alpha",
            "source_hypothesis": {
                "winner_strategy_id": "alpha",
                "suggested_action": "review_role_priority",
            },
            "allocation_profile_overrides": {
                "strategies": {"alpha": {"portfolio": {"role_priority": 20}}}
            },
        }
    ]

    payload = build_summary_payload(
        allocation_summary_json=tmp_path / "allocation.json",
        selected_windows=("2016_2021", "2016_2025"),
        generated_cases=generated_cases,
        baseline_payload=baseline_payload,
        case_payloads=case_payloads,
        run_dir=tmp_path,
    )

    case = payload["cases"][0]
    pre = case["windows"][0]
    full = case["windows"][1]
    assert pre["delta_vs_baseline"]["pf"] == 0.05
    assert pre["delta_vs_baseline"]["max_drawdown"] == -0.01
    assert full["delta_vs_baseline"]["avg_r"] == 0.01


def test_render_summary_md_lists_cases() -> None:
    payload = {
        "generated_at_utc": "2026-03-17T12:00:00+00:00",
        "allocation_summary_json": "reports/gui/runtime/allocation_summary.json",
        "selected_windows": ["2016_2021", "2016_2025"],
        "cases": [
            {
                "case_id": "demote_alpha_role_priority",
                "source_hypothesis": {"suggested_action": "review_role_priority"},
                "windows": [
                    {
                        "window_name": "2016_2021",
                        "case": {"summary": {"pf": 1.05}},
                        "delta_vs_baseline": {"pf": 0.05},
                    },
                    {
                        "window_name": "2016_2025",
                        "case": {"summary": {"pf": 1.12}},
                        "delta_vs_baseline": {"pf": 0.02},
                    },
                ],
            }
        ],
    }

    rendered = render_summary_md(payload)

    assert "Allocator Tuning Review" in rendered
    assert "demote_alpha_role_priority" in rendered
    assert "review_role_priority" in rendered
    assert "1.05" in rendered
