from __future__ import annotations

import json
from pathlib import Path

from src.portfolio.allocation_review import (
    apply_allocation_profile_overrides,
    build_allocator_hypotheses,
    build_allocator_tuning_cases,
    load_allocation_review_payload,
)


def test_load_allocation_review_payload_reads_json(tmp_path: Path) -> None:
    path = tmp_path / "allocation_summary.json"
    path.write_text(
        json.dumps({"winner_review_summary": [{"winner_strategy_id": "alpha"}]}),
        encoding="utf-8",
    )

    payload = load_allocation_review_payload(path)

    assert payload is not None
    assert payload["winner_review_summary"][0]["winner_strategy_id"] == "alpha"


def test_build_allocator_hypotheses_filters_and_sorts() -> None:
    payload = {
        "winner_review_summary": [
            {
                "winner_strategy_id": "alpha",
                "winner_portfolio_group": "usd_jpy_breakout",
                "winner_exposure_bucket": "usd_jpy_long",
                "count": 4,
                "share_pct": 66.7,
                "top_reason_code": "tie_break_lost",
                "suggested_action": "review_role_priority",
            },
            {
                "winner_strategy_id": "beta",
                "winner_portfolio_group": "us_pullback",
                "winner_exposure_bucket": "usd_jpy_short",
                "count": 1,
                "share_pct": 16.7,
                "top_reason_code": "active_group_deferred",
                "suggested_action": "review_tie_break",
            },
        ]
    }

    hypotheses = build_allocator_hypotheses(payload, focus_strategy_ids={"alpha"})

    assert hypotheses == [
        {
            "winner_strategy_id": "alpha",
            "winner_portfolio_group": "usd_jpy_breakout",
            "winner_exposure_bucket": "usd_jpy_long",
            "count": 4,
            "share_pct": 66.7,
            "top_reason_code": "tie_break_lost",
            "suggested_action": "review_role_priority",
            "summary": "alpha dominates conflicts (4, 66.7%) via tie_break_lost",
        }
    ]


def test_build_allocator_tuning_cases_builds_role_and_tie_break_cases() -> None:
    allocation_summary = {
        "winner_review_summary": [
            {
                "winner_strategy_id": "alpha",
                "winner_portfolio_group": "usd_jpy_breakout",
                "winner_exposure_bucket": "usd_jpy_long",
                "count": 4,
                "share_pct": 66.7,
                "top_reason_code": "tie_break_lost",
                "suggested_action": "review_role_priority",
            },
            {
                "winner_strategy_id": "beta",
                "winner_portfolio_group": "usd_jpy_pullback",
                "winner_exposure_bucket": "usd_jpy_pullback_long",
                "count": 2,
                "share_pct": 22.2,
                "top_reason_code": "selection_limit",
                "suggested_action": "review_tie_break",
            },
        ]
    }
    allocation_config = {
        "active_profile": "portfolio_admission_v2",
        "profiles": {
            "portfolio_admission_v2": {
                "tie_break": ["score_desc", "role_priority_asc", "priority_asc", "strategy_id_asc"],
                "global": {"portfolio": {"role_priority": 100}},
                "strategies": {
                    "alpha": {"portfolio": {"role_priority": 10}},
                    "beta": {"portfolio": {"role_priority": 20}},
                },
            }
        },
    }

    cases = build_allocator_tuning_cases(
        allocation_summary,
        allocation_config_payload_or_path=allocation_config,
        allocation_profile="portfolio_admission_v2",
    )

    assert [case["case_id"] for case in cases] == [
        "demote_alpha_role_priority",
        "retie_beta",
    ]
    assert cases[0]["allocation_profile_overrides"]["strategies"]["alpha"]["portfolio"]["role_priority"] == 20
    assert cases[1]["allocation_profile_overrides"]["tie_break"] == [
        "role_priority_asc",
        "score_desc",
        "priority_asc",
        "strategy_id_asc",
    ]


def test_apply_allocation_profile_overrides_merges_strategy_payload() -> None:
    base = {
        "active_profile": "portfolio_admission_v2",
        "profiles": {
            "portfolio_admission_v2": {
                "tie_break": ["score_desc", "role_priority_asc"],
                "strategies": {
                    "alpha": {"portfolio": {"role_priority": 10, "slot_cost": 0.01}},
                },
            }
        },
    }

    updated = apply_allocation_profile_overrides(
        base,
        allocation_profile="portfolio_admission_v2",
        overrides={"strategies": {"alpha": {"portfolio": {"role_priority": 20}}}},
    )

    profile = updated["profiles"]["portfolio_admission_v2"]
    assert updated["active_profile"] == "portfolio_admission_v2"
    assert profile["strategies"]["alpha"]["portfolio"]["role_priority"] == 20
    assert profile["strategies"]["alpha"]["portfolio"]["slot_cost"] == 0.01
