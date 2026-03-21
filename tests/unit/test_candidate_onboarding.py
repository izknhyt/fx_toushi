from __future__ import annotations

from pathlib import Path

from src.portfolio.candidate_onboarding import (
    build_candidate_onboarding_decision_summary,
    build_candidate_onboarding_packet,
    build_candidate_onboarding_promotion_gate_summary,
    materialize_candidate_onboarding_promotion_packet,
    render_candidate_onboarding_packet_md,
)
from tools.run_portfolio_candidate_onboarding_exec import run_candidate_onboarding


def test_build_candidate_onboarding_packet_includes_canonical_sections(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "strategies:",
                "  alpha:",
                "    enabled: true",
                "  beta:",
                "    enabled: false",
                "  gamma:",
                "    enabled: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    packet = build_candidate_onboarding_packet(
        manifest_path=manifest_path,
        allocation_config_path=tmp_path / "allocation.yaml",
        allocation_profile="portfolio_admission_v2",
        data_path=tmp_path / "merged.parquet",
        candidate_strategy_ids=["candidate_a"],
        baseline_strategy_ids=None,
        output_dir=tmp_path / "out",
        output_prefix="portfolio_candidate_onboarding",
        runner_command="tradectl portfolio candidate-onboard --candidate-strategies candidate_a",
    )

    assert packet["packet_version"] == "candidate_onboarding.v1"
    assert packet["status"] == "ready"
    assert packet["runbook_ref"].endswith("PORTFOLIO-CANDIDATE-02.md")
    assert packet["baseline_strategy_ids"] == ["alpha", "gamma"]
    assert packet["candidate_onboarding"]["baseline"]["strategy_ids"] == ["alpha", "gamma"]
    assert packet["candidate_onboarding"]["candidate"]["strategy_ids"] == ["candidate_a"]
    assert packet["candidate_onboarding"]["standalone_result"]["status"] == "pending"
    assert packet["candidate_onboarding"]["shadow_readiness_result"]["status"] == "pending"
    assert packet["candidate_onboarding"]["recommended_action"] == "run_candidate_onboarding"
    assert packet["candidate_onboarding_result_summary"]["decision_status"] == "pending"
    assert packet["candidate_onboarding_promotion_gate_summary"]["promotion_gate_status"] == "blocked"
    assert "tradectl portfolio candidate-onboard" in packet["runner_command"]
    assert packet["commands"][1]["step"] == "portfolio_review"


def test_render_candidate_onboarding_packet_md_contains_candidate_sections() -> None:
    rendered = render_candidate_onboarding_packet_md(
        {
            "packet_version": "candidate_onboarding.v1",
            "phase": "candidate_onboarding",
            "status": "ready",
            "runbook_ref": "docs/runbooks/PORTFOLIO-CANDIDATE-01.md",
            "runner_command": "tradectl portfolio candidate-onboard --candidate-strategies alpha",
            "required_inputs": [],
            "baseline_strategy_ids": ["alpha", "gamma"],
            "candidate_strategy_ids": ["candidate_a"],
            "windows": ["2016_2021", "2016_2025"],
            "candidate_onboarding": {
                "baseline": {"count": 2},
                "candidate": {"count": 1},
                "recommended_action": "run_candidate_onboarding",
                "standalone_result": {"status": "pending"},
                "marginal_contribution_result": {"status": "pending"},
                "shadow_readiness_result": {"status": "pending"},
            },
            "commands": [{"step": "portfolio_evaluate", "command": "tradectl portfolio evaluate"}],
            "artifacts": {"review_summary_json": "reports/analysis/shadow/review.json"},
        }
    )

    assert "Candidate Onboarding Execution Packet" in rendered
    assert "portfolio_candidate_onboard" not in rendered
    assert "candidate_a" in rendered
    assert "recommended_action" in rendered
    assert "portfolio_evaluate" in rendered


def test_run_portfolio_candidate_onboarding_renders_packet(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "strategies:",
                "  alpha:",
                "    enabled: true",
                "  gamma:",
                "    enabled: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = run_candidate_onboarding(
        manifest_path=manifest_path,
        allocation_config_path=tmp_path / "allocation.yaml",
        allocation_profile="portfolio_admission_v2",
        data_path=tmp_path / "merged.parquet",
        candidate_strategies=["candidate_a"],
        baseline_strategies=None,
        windows=("2016_2021", "2016_2025"),
        output_dir=tmp_path / "out",
        output_prefix="portfolio_candidate_onboarding",
        run=False,
    )

    assert payload["status"] == "ok"
    assert payload["packet"]["eligibility_status"] == "blocked"
    assert payload["packet"]["execution_status"] == "planned"
    assert payload["packet"]["runner_command"].startswith("tradectl portfolio candidate-onboard")
    assert Path(payload["json_path"]).exists()
    assert Path(payload["markdown_path"]).exists()


def test_candidate_onboarding_gate_promotes_ready_candidate(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "strategies:",
                "  alpha:",
                "    enabled: true",
                "  candidate_a:",
                "    enabled: false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    packet = build_candidate_onboarding_packet(
        manifest_path=manifest_path,
        allocation_config_path=tmp_path / "allocation.yaml",
        allocation_profile="portfolio_admission_v2",
        data_path=tmp_path / "merged.parquet",
        candidate_strategy_ids=["candidate_a"],
        baseline_strategy_ids=["alpha"],
        output_dir=tmp_path / "out",
        output_prefix="portfolio_candidate_onboarding",
        runner_command="tradectl portfolio candidate-onboard --candidate-strategies candidate_a",
    )
    packet["candidate_onboarding_result_summary"] = {
        "status": "ok",
        "decision_status": "promote",
        "promotion_candidate": True,
        "promotion_next_action": "promote_candidate_to_baseline",
        "candidate_count": 1,
        "promote_count": 1,
        "research_only_count": 0,
        "reject_count": 0,
        "candidate_decisions": [
            {
                "candidate_strategy_id": "candidate_a",
                "decision_status": "promote",
                "reason_codes": ["all_windows_improved"],
                "promotion_candidate": True,
            }
        ],
        "baseline_strategy_ids": ["alpha"],
        "candidate_strategy_ids": ["candidate_a"],
        "windows": ["2016_2021", "2016_2025"],
        "shadow_readiness_status": "ready",
        "runtime_guardrail_status": "ready",
        "rollout_suppression_status": "inactive",
        "shadow_feedback_recovery_resolution_status": "resolved",
    }
    gate = build_candidate_onboarding_promotion_gate_summary(
        packet["candidate_onboarding_result_summary"],
        rollout_suppression_summary={"status": "inactive", "active": False},
        recovery_execution_state={"resolution_status": "resolved"},
        runtime_guardrail_summary={"status": "ready"},
    )
    assert gate["promotion_gate_status"] == "eligible"
    assert gate["promotion_eligible"] is True
    promotion_packet = materialize_candidate_onboarding_promotion_packet(
        packet,
        manifest_path=manifest_path,
        output_dir=tmp_path / "out",
    )
    assert promotion_packet["status"] == "ready"
    assert promotion_packet["promote_strategy_ids"] == ["candidate_a"]
