from __future__ import annotations

from src.portfolio.shadow_next_stage_template import build_shadow_next_stage_execution_template


def test_build_shadow_next_stage_execution_template_returns_candidate_onboarding_template() -> None:
    template = build_shadow_next_stage_execution_template(
        {
            "soak_summary": {
                "ready_for_transition": True,
                "qualified_next_phase": "candidate_onboarding",
            }
        }
    )

    assert template["status"] == "ready"
    assert template["phase"] == "candidate_onboarding"
    assert template["runbook_ref"].endswith("PORTFOLIO-CANDIDATE-01.md")
    assert "tradectl portfolio next-stage --phase candidate_onboarding" in template["runner_command"]
    assert template["commands"]
    assert any("portfolio evaluate" in item for item in template["commands"])


def test_build_shadow_next_stage_execution_template_returns_multi_pair_template() -> None:
    template = build_shadow_next_stage_execution_template(
        {
            "soak_summary": {
                "ready_for_transition": True,
                "qualified_next_phase": "multi_pair_preparation",
            }
        }
    )

    assert template["status"] == "ready"
    assert template["phase"] == "multi_pair_preparation"
    assert template["runbook_ref"].endswith("PORTFOLIO-MULTIPAIR-01.md")
    assert "tradectl portfolio next-stage --phase multi_pair_preparation" in template["runner_command"]
    assert template["checklist"]


def test_build_shadow_next_stage_execution_template_returns_pending_template_when_not_ready() -> None:
    template = build_shadow_next_stage_execution_template(
        {
            "soak_summary": {
                "ready_for_transition": False,
                "qualified_next_phase": "continue_shadow",
                "reasons": ["stage_gate_recommendation_streak_below_threshold"],
            }
        }
    )

    assert template["status"] == "pending"
    assert template["phase"] == "continue_shadow"
    assert template["runbook_ref"].endswith("RUN-SHADOW-01.md")
    assert template["notes"] == ["stage_gate_recommendation_streak_below_threshold"]
