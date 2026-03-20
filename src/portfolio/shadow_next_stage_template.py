"""Execution templates for qualified shadow soak next-stage transitions."""

from __future__ import annotations

from typing import Any, Mapping

DEFAULT_SHADOW_NEXT_STAGE_TEMPLATE_ID = "shadow.next_stage.template.v1"


def build_shadow_next_stage_execution_template(summary: Mapping[str, Any]) -> dict[str, Any]:
    soak = _mapping(summary.get("soak_summary"))
    qualified_next_phase = str(soak.get("qualified_next_phase") or "continue_shadow")
    ready = bool(soak.get("ready_for_transition"))

    if ready and qualified_next_phase == "candidate_onboarding":
        return {
            "status": "ready",
            "template_id": DEFAULT_SHADOW_NEXT_STAGE_TEMPLATE_ID,
            "phase": "candidate_onboarding",
            "title": "Candidate onboarding execution template",
            "next_action": "advance_to_candidate_onboarding",
            "runbook_ref": "docs/runbooks/PORTFOLIO-CANDIDATE-01.md",
            "runner_command": (
                "tradectl portfolio next-stage --phase candidate_onboarding "
                "--candidate-strategies <candidate_ids> --data-path <merged_parquet>"
            ),
            "checklist": [
                "Pick the candidate strategy ids to compare against the fixed USDJPY baseline.",
                "Run standalone evidence on focused windows before portfolio comparison.",
                "Run marginal contribution against the baseline portfolio and record delta_vs_baseline.",
                "Review failed windows before deciding promote, research-only, or reject.",
                "Only schedule shadow-readiness checks if the candidate survives standalone and marginal contribution gates.",
            ],
            "commands": [
                "python3 tools/run_long_horizon_portfolio_validation.py --manifest config/strategy_manifest.parallel_portfolio_v2.yaml --windows 2016_2021,2016_2025 --strategies <candidate_ids>",
                "tradectl portfolio evaluate --baseline-strategies <baseline_ids> --candidate-strategies <candidate_ids> --windows 2016_2021,2016_2025,2022_2025",
                "tradectl portfolio review --summary-json <standalone_summary_json>",
            ],
            "evidence_targets": [
                "reports/validation_log/portfolio_candidate_eval_<stamp>.json",
                "reports/analysis/portfolio_candidate_eval_<stamp>.md",
            ],
            "notes": [
                "Use the fixed USDJPY baseline portfolio as the comparison target.",
                "Do not promote based on standalone PF alone; require positive marginal contribution.",
            ],
        }
    if ready and qualified_next_phase == "multi_pair_preparation":
        return {
            "status": "ready",
            "template_id": DEFAULT_SHADOW_NEXT_STAGE_TEMPLATE_ID,
            "phase": "multi_pair_preparation",
            "title": "Multi-pair preparation execution template",
            "next_action": "advance_to_multi_pair_preparation",
            "runbook_ref": "docs/runbooks/PORTFOLIO-MULTIPAIR-01.md",
            "runner_command": (
                "tradectl portfolio next-stage --phase multi_pair_preparation "
                "--next-symbol <symbol> --data-path <merged_parquet>"
            ),
            "checklist": [
                "Choose the next pair and verify curated data coverage and spread assumptions.",
                "Run the current portfolio kernel on the new pair in standalone mode first.",
                "Check exposure bucket, portfolio group, and candidate schema compatibility for the new pair.",
                "Compare baseline USDJPY-only utility against a pilot multi-pair portfolio before promotion.",
                "Prepare shadow monitoring surfaces for the new pair before enabling it in the baseline manifest.",
            ],
            "commands": [
                "python3 tools/run_long_horizon_portfolio_validation.py --manifest config/strategy_manifest.parallel_portfolio_v2.yaml --windows 2016_2025,2022_2025",
                "tradectl portfolio candidates --manifest config/strategy_manifest.parallel_portfolio_v2.yaml",
                "tradectl portfolio admit --manifest config/strategy_manifest.parallel_portfolio_v2.yaml",
            ],
            "evidence_targets": [
                "reports/validation_log/long_horizon_portfolio_<stamp>_<window>.json",
                "reports/analysis/usdjpy_long_horizon_review_<stamp>.md",
            ],
            "notes": [
                "Preserve the same candidate/admission contract when adding a second pair.",
                "Treat the first multi-pair activation as a shadow-first rollout, not a direct baseline promotion.",
            ],
        }
    return {
        "status": "pending",
        "template_id": DEFAULT_SHADOW_NEXT_STAGE_TEMPLATE_ID,
        "phase": "continue_shadow",
        "title": "Continue shadow soak",
        "next_action": "continue_shadow",
        "runbook_ref": "docs/runbooks/RUN-SHADOW-01.md",
        "runner_command": "",
        "checklist": [
            "Keep collecting daily shadow reviews until the same next phase remains qualified for the required streak.",
            "Resolve open discrepancies before attempting the next stage.",
        ],
        "commands": [],
        "evidence_targets": [
            "reports/analysis/shadow/daily_shadow_review_<stamp>.md",
            "reports/analysis/shadow/daily_shadow_ops_summary_<stamp>.md",
        ],
        "notes": [str(item) for item in (soak.get("reasons") or []) if str(item).strip()],
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = [
    "DEFAULT_SHADOW_NEXT_STAGE_TEMPLATE_ID",
    "build_shadow_next_stage_execution_template",
]
