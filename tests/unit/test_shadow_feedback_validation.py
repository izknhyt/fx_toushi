from __future__ import annotations

from pathlib import Path

from src.portfolio.shadow_feedback_validation import (
    build_shadow_feedback_validation_case,
    build_shadow_feedback_validation_summary,
    materialize_shadow_feedback_override_config,
    resolve_shadow_feedback_focused_windows,
)


def test_resolve_shadow_feedback_focused_windows_prefers_packet_windows() -> None:
    packet = {"focused_validation": {"windows": ["2016_2021", "2016_2025"]}}

    assert resolve_shadow_feedback_focused_windows(packet) == ("2016_2021", "2016_2025")


def test_build_shadow_feedback_validation_case_returns_none_without_overrides() -> None:
    assert build_shadow_feedback_validation_case({"focused_validation": {"windows": []}}) is None


def test_build_shadow_feedback_validation_case_returns_packet_case() -> None:
    case = build_shadow_feedback_validation_case(
        {
            "allocation_profile_overrides": {"global": {"score": {"min_score": 0.55}}},
            "feedback_loop_state": "stabilize_baseline",
            "next_action": "review_allocator_feedback_candidates",
            "runtime_guardrail": {"status": "guarded"},
            "focused_validation": {"windows": ["2016_2021", "2016_2025"]},
        }
    )

    assert case is not None
    assert case["case_id"] == "shadow_feedback_override"
    assert case["allocation_profile_overrides"]["global"]["score"]["min_score"] == 0.55


def test_materialize_shadow_feedback_override_config_merges_overrides() -> None:
    packet = {
        "allocation_profile_overrides": {
            "global": {"score": {"min_score": 0.55}},
            "strategies": {"alpha": {"portfolio": {"role_priority": 15}}},
        }
    }
    config = materialize_shadow_feedback_override_config(
        packet,
        allocation_config_payload_or_path={
            "profiles": {
                "portfolio_admission_v2": {
                    "global": {"score": {"min_score": 0.5}, "portfolio": {"slot_cost": 0.02}},
                    "strategies": {"alpha": {"portfolio": {"role_priority": 20}}},
                }
            }
        },
        allocation_profile="portfolio_admission_v2",
    )

    assert config is not None
    assert config["profiles"]["portfolio_admission_v2"]["global"]["score"]["min_score"] == 0.55
    assert config["profiles"]["portfolio_admission_v2"]["strategies"]["alpha"]["portfolio"]["role_priority"] == 15


def test_build_shadow_feedback_validation_summary_classifies_adopt() -> None:
    packet = {
        "focused_validation": {"windows": ["2016_2021", "2016_2025"]},
        "runtime_guardrail": {"status": "guarded"},
    }
    baseline = {
        "results": [
            {
                "window_name": "2016_2021",
                "summary": {"pf": 1.0, "avg_r": 0.01, "trades": 100, "win_rate": 0.45, "max_drawdown": 0.10},
                "acceptance": {"status": "pass"},
            },
            {
                "window_name": "2016_2025",
                "summary": {"pf": 1.1, "avg_r": 0.02, "trades": 150, "win_rate": 0.46, "max_drawdown": 0.12},
                "acceptance": {"status": "pass"},
            },
        ]
    }
    override = {
        "results": [
            {
                "window_name": "2016_2021",
                "summary": {"pf": 1.05, "avg_r": 0.02, "trades": 102, "win_rate": 0.47, "max_drawdown": 0.09},
                "acceptance": {"status": "pass"},
            },
            {
                "window_name": "2016_2025",
                "summary": {"pf": 1.15, "avg_r": 0.03, "trades": 155, "win_rate": 0.47, "max_drawdown": 0.11},
                "acceptance": {"status": "pass"},
            },
        ]
    }

    summary = build_shadow_feedback_validation_summary(
        packet=packet,
        baseline_payload=baseline,
        override_payload=override,
        selected_windows=("2016_2021", "2016_2025"),
    )

    assert summary["validation_decision"] == "adopt"
    assert summary["runtime_guardrail_candidate"]["status"] == "armed"


def test_build_shadow_feedback_validation_summary_classifies_reject() -> None:
    summary = build_shadow_feedback_validation_summary(
        packet={},
        baseline_payload={
            "results": [
                {
                    "window_name": "2016_2025",
                    "summary": {"pf": 1.1, "avg_r": 0.02, "trades": 150, "win_rate": 0.46, "max_drawdown": 0.12},
                    "acceptance": {"status": "pass"},
                }
            ]
        },
        override_payload={
            "results": [
                {
                    "window_name": "2016_2025",
                    "summary": {"pf": 1.0, "avg_r": 0.01, "trades": 150, "win_rate": 0.45, "max_drawdown": 0.15},
                    "acceptance": {"status": "fail"},
                }
            ]
        },
        selected_windows=("2016_2025",),
    )

    assert summary["validation_decision"] == "reject"
    assert "full_history_regressed" in summary["decision_reasons"]
