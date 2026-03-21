from __future__ import annotations

import json
from pathlib import Path

from src.ops.shadow_next_stage import (
    DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_COMMAND,
    append_shadow_next_stage_execution,
    build_shadow_next_stage_execution_summary,
    latest_shadow_next_stage_execution,
    load_shadow_next_stage_automation_config,
)


def test_build_shadow_next_stage_execution_summary_builds_candidate_command(tmp_path: Path) -> None:
    config_path = tmp_path / "shadow_next_stage_automation.yaml"
    config_path.write_text(
        "\n".join(
            [
                "shared:",
                "  manifest_path: config/strategy_manifest.parallel_portfolio_v2.yaml",
                "  allocation_config_path: config/strategy_allocation.yaml",
                "  allocation_profile: portfolio_admission_v2",
                "  output_dir: reports/analysis/shadow",
                f"  data_path: {tmp_path / 'merged.parquet'}",
                "candidate_onboarding:",
                "  candidate_strategies: [alpha_candidate]",
                "  baseline_strategies: [m1_asia_compression_expansion_breakout,m1_us_session_trend_pullback]",
                "  windows: [2016_2021, 2016_2025, 2022_2025]",
            ]
        ),
        encoding="utf-8",
    )

    summary = build_shadow_next_stage_execution_summary(
        daily_shadow_ops_summary={
            "review_date_utc": "2026-03-20",
            "next_stage_template_status": "ready",
            "next_stage_template_phase": "candidate_onboarding",
            "next_stage_template_runbook_ref": "docs/runbooks/PORTFOLIO-CANDIDATE-01.md",
        },
        automation_config=load_shadow_next_stage_automation_config(config_path),
        execution_history=[],
    )

    assert summary["status"] == "ready_to_run"
    assert summary["should_execute"] is True
    assert summary["automation_command"] == DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_COMMAND
    assert "--phase candidate_onboarding" in summary["execution_command"]
    assert "--candidate-strategies alpha_candidate" in summary["execution_command"]
    assert "--run" in summary["execution_command"]


def test_build_shadow_next_stage_execution_summary_skips_duplicate_completion() -> None:
    summary = build_shadow_next_stage_execution_summary(
        daily_shadow_ops_summary={
            "review_date_utc": "2026-03-20",
            "next_stage_template_status": "ready",
            "next_stage_template_phase": "multi_pair_preparation",
            "next_stage_template_runbook_ref": "docs/runbooks/PORTFOLIO-MULTIPAIR-01.md",
        },
        automation_config={
            "shared": {
                "manifest_path": "config/strategy_manifest.parallel_portfolio_v2.yaml",
                "allocation_config_path": "config/strategy_allocation.yaml",
                "allocation_profile": "portfolio_admission_v2",
                "output_dir": "reports/analysis/shadow",
                "data_path": "/tmp/merged.parquet",
            },
            "multi_pair_preparation": {
                "next_symbol": "EURUSD",
                "windows": ["2016_2025", "2022_2025"],
            },
        },
        execution_history=[
            {
                "event": "shadow.next_stage.execution",
                "ts": "2026-03-20T00:10:00Z",
                "review_date_utc": "2026-03-20",
                "phase": "multi_pair_preparation",
                "status": "completed",
            }
        ],
    )

    assert summary["status"] == "skipped_duplicate"
    assert summary["already_executed_today"] is True
    assert summary["should_execute"] is False


def test_build_shadow_next_stage_execution_summary_blocks_runtime_guardrail() -> None:
    summary = build_shadow_next_stage_execution_summary(
        daily_shadow_ops_summary={
            "review_date_utc": "2026-03-20",
            "next_stage_template_status": "ready",
            "next_stage_template_phase": "candidate_onboarding",
            "next_stage_template_runbook_ref": "docs/runbooks/PORTFOLIO-CANDIDATE-01.md",
        },
        automation_config={
            "shared": {
                "manifest_path": "config/strategy_manifest.parallel_portfolio_v2.yaml",
                "allocation_config_path": "config/strategy_allocation.yaml",
                "allocation_profile": "portfolio_admission_v2",
                "output_dir": "reports/analysis/shadow",
                "data_path": "/tmp/merged.parquet",
            },
            "candidate_onboarding": {
                "baseline_strategies": ["m1_asia_compression_expansion_breakout"],
                "candidate_strategies": ["shadow_feedback_override"],
                "windows": ["2016_2021", "2016_2025"],
            },
        },
        execution_history=[],
        shadow_feedback_override_packet={
            "status": "ok",
            "runtime_guardrail": {
                "status": "guarded",
                "freeze_next_stage": True,
                "recommended_action": "retain_current_profile",
                "reasons": ["open_discrepancies"],
            },
        },
    )

    assert summary["status"] == "blocked_by_runtime_guardrail"
    assert summary["status_reason"] == "shadow_runtime_guardrail_blocked"
    assert summary["should_execute"] is False
    assert summary["guardrail_blocked"] is True
    assert summary["runtime_guardrail_summary"]["status"] == "guarded"


def test_build_shadow_next_stage_execution_summary_blocks_manual_clear_guardrail() -> None:
    summary = build_shadow_next_stage_execution_summary(
        daily_shadow_ops_summary={
            "review_date_utc": "2026-03-20",
            "next_stage_template_status": "ready",
            "next_stage_template_phase": "candidate_onboarding",
            "next_stage_template_runbook_ref": "docs/runbooks/PORTFOLIO-CANDIDATE-01.md",
        },
        automation_config={
            "shared": {
                "manifest_path": "config/strategy_manifest.parallel_portfolio_v2.yaml",
                "allocation_config_path": "config/strategy_allocation.yaml",
                "allocation_profile": "portfolio_admission_v2",
                "output_dir": "reports/analysis/shadow",
                "data_path": "/tmp/merged.parquet",
            },
            "candidate_onboarding": {
                "baseline_strategies": ["m1_asia_compression_expansion_breakout"],
                "candidate_strategies": ["shadow_feedback_override"],
                "windows": ["2016_2021", "2016_2025"],
            },
        },
        execution_history=[],
        shadow_feedback_override_packet={
            "status": "blocked",
            "runtime_guardrail": {
                "status": "blocked",
                "freeze_next_stage": True,
                "manual_clear_required": True,
                "recommended_action": "review_or_stop_rollout",
                "reasons": ["validation_execution_mismatch"],
            },
        },
    )

    assert summary["status"] == "blocked_by_runtime_guardrail"
    assert summary["status_reason"] == "shadow_runtime_guardrail_manual_clear_required"
    assert summary["should_execute"] is False
    assert summary["guardrail_blocked"] is True
    assert summary["manual_clear_required"] is True
    assert summary["runtime_guardrail_summary"]["status"] == "blocked"


def test_build_shadow_next_stage_execution_summary_blocks_rollout_suppression() -> None:
    summary = build_shadow_next_stage_execution_summary(
        daily_shadow_ops_summary={
            "review_date_utc": "2026-03-20",
            "next_stage_template_status": "ready",
            "next_stage_template_phase": "candidate_onboarding",
            "next_stage_template_runbook_ref": "docs/runbooks/PORTFOLIO-CANDIDATE-01.md",
            "rollout_suppression_summary": {
                "status": "active",
                "active": True,
                "scope": "candidate_onboarding",
                "recommended_action": "execute_recovery_packet",
            },
        },
        automation_config={
            "shared": {
                "manifest_path": "config/strategy_manifest.parallel_portfolio_v2.yaml",
                "allocation_config_path": "config/strategy_allocation.yaml",
                "allocation_profile": "portfolio_admission_v2",
                "output_dir": "reports/analysis/shadow",
                "data_path": "/tmp/merged.parquet",
            },
            "candidate_onboarding": {
                "baseline_strategies": ["m1_asia_compression_expansion_breakout"],
                "candidate_strategies": ["shadow_feedback_override"],
                "windows": ["2016_2021", "2016_2025"],
            },
        },
        execution_history=[],
    )

    assert summary["status"] == "blocked_by_rollout_suppression"
    assert summary["status_reason"] == "execute_recovery_packet"
    assert summary["should_execute"] is False
    assert summary["suppression_active"] is True


def test_append_and_load_shadow_next_stage_execution_round_trip(tmp_path: Path) -> None:
    ledger_path = tmp_path / "shadow_next_stage_execution.jsonl"
    append_shadow_next_stage_execution(
        {
            "review_date_utc": "2026-03-20",
            "phase": "candidate_onboarding",
            "status": "completed",
            "runner_command": "tradectl portfolio next-stage --phase candidate_onboarding --run",
            "automation_command": DEFAULT_SHADOW_NEXT_STAGE_AUTOMATION_COMMAND,
        },
        ledger_path,
    )
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["event"] == "shadow.next_stage.execution"
    latest = latest_shadow_next_stage_execution(rows, review_date_utc="2026-03-20", phase="candidate_onboarding")
    assert latest is not None
    assert latest["status"] == "completed"
