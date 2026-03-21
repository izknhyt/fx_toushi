from __future__ import annotations

from pathlib import Path

from src.portfolio.shadow_next_stage_runner import (
    build_candidate_onboarding_execution_packet,
    build_multi_pair_preparation_execution_packet,
    render_shadow_next_stage_execution_packet_md,
)


def test_build_candidate_onboarding_execution_packet_infers_baseline_from_manifest(tmp_path: Path) -> None:
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

    packet = build_candidate_onboarding_execution_packet(
        manifest_path=manifest_path,
        allocation_config_path=tmp_path / "allocation.yaml",
        allocation_profile="portfolio_admission_v2",
        data_path=tmp_path / "merged.parquet",
        candidate_strategy_ids=["candidate_a"],
        baseline_strategy_ids=None,
        output_dir=tmp_path / "out",
    )

    assert packet["status"] == "ready"
    assert packet["runbook_ref"].endswith("PORTFOLIO-CANDIDATE-01.md")
    assert "tradectl portfolio next-stage" in packet["runner_command"]
    assert packet["baseline_strategy_ids"] == ["alpha", "gamma"]
    assert packet["commands"][0]["step"] == "portfolio_evaluate"
    assert packet["commands"][1]["step"] == "portfolio_review"


def test_build_multi_pair_preparation_execution_packet_requires_symbol_and_data() -> None:
    packet = build_multi_pair_preparation_execution_packet(
        manifest_path=Path("config/strategy_manifest.parallel_portfolio_v2.yaml"),
        allocation_config_path=Path("config/strategy_allocation.yaml"),
        allocation_profile="portfolio_admission_v2",
        data_path=None,
        next_symbol=None,
        profile_path=Path("config/profiles/paper.yaml"),
        data_dir=Path("data/research/curated"),
        feature_config=Path("config/feature_pipeline.yaml"),
        data_manifest=Path("reports/data_manifest.json"),
        output_dir=Path("reports/analysis/shadow"),
    )

    assert packet["status"] == "pending_inputs"
    assert packet["required_inputs"] == ["next_symbol", "data_path"]
    assert packet["runbook_ref"].endswith("PORTFOLIO-MULTIPAIR-01.md")


def test_render_shadow_next_stage_execution_packet_md_contains_runner_and_artifacts() -> None:
    text = render_shadow_next_stage_execution_packet_md(
        {
            "phase": "candidate_onboarding",
            "status": "ready",
            "runbook_ref": "docs/runbooks/PORTFOLIO-CANDIDATE-01.md",
            "runner_command": "tradectl portfolio next-stage --phase candidate_onboarding",
            "required_inputs": [],
            "commands": [{"step": "portfolio_evaluate", "command": "tradectl portfolio evaluate"}],
            "artifacts": {"evaluation_summary_json": "reports/analysis/shadow/eval.json"},
        }
    )

    assert "Shadow Next Stage Execution Packet" in text
    assert "PORTFOLIO-CANDIDATE-01.md" in text
    assert "tradectl portfolio next-stage --phase candidate_onboarding" in text
    assert "evaluation_summary_json" in text
