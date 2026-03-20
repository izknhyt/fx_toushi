from __future__ import annotations

from src.portfolio.shadow_feedback_template import build_shadow_feedback_validation_template


def test_build_shadow_feedback_validation_template_returns_ready_command() -> None:
    template = build_shadow_feedback_validation_template(
        {
            "status": "ok",
            "allocation_profile_overrides": {"global": {"score": {"min_score": 1.1}}},
            "focused_validation": {"status": "recommended", "windows": ["2016_2021", "2016_2025"]},
            "runtime_guardrail": {"status": "guarded"},
        }
    )

    assert template["status"] == "pending_inputs"
    assert template["next_action"] == "run_focused_validation"
    assert template["runbook_ref"].endswith("PORTFOLIO-SHADOW-FEEDBACK-01.md")
    assert "tradectl portfolio shadow-feedback-validate" in template["runner_command"]


def test_build_shadow_feedback_validation_template_returns_not_required_without_overrides() -> None:
    template = build_shadow_feedback_validation_template({"status": "no_changes"})

    assert template["status"] == "not_required"
    assert template["runner_command"] == ""
