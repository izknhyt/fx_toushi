"""Build automation-ready execution packets for qualified shadow next stages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import yaml

DEFAULT_NEXT_STAGE_WINDOWS = ("2016_2021", "2016_2025", "2022_2025")
DEFAULT_MULTI_PAIR_WINDOWS = ("2016_2025", "2022_2025")
DEFAULT_CANDIDATE_RUNBOOK = "docs/runbooks/PORTFOLIO-CANDIDATE-01.md"
DEFAULT_MULTI_PAIR_RUNBOOK = "docs/runbooks/PORTFOLIO-MULTIPAIR-01.md"


def build_candidate_onboarding_execution_packet(
    *,
    manifest_path: Path,
    allocation_config_path: Path,
    allocation_profile: str,
    data_path: Path | None,
    candidate_strategy_ids: list[str],
    baseline_strategy_ids: list[str] | None = None,
    windows: tuple[str, ...] = DEFAULT_NEXT_STAGE_WINDOWS,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    baseline_ids = list(baseline_strategy_ids or _resolve_enabled_strategy_ids(manifest_path))
    required_inputs: list[str] = []
    if not candidate_strategy_ids:
        required_inputs.append("candidate_strategy_ids")
    if data_path is None:
        required_inputs.append("data_path")

    output_dir = output_dir or (Path("reports") / "analysis" / "shadow" / "next_stage")
    output_prefix = "shadow_candidate_onboarding"
    standalone_json = output_dir / f"{output_prefix}_standalone.json"
    standalone_md = output_dir / f"{output_prefix}_standalone.md"
    evaluate_json = output_dir / f"{output_prefix}_evaluation.json"
    evaluate_md = output_dir / f"{output_prefix}_evaluation.md"
    review_json = output_dir / f"{output_prefix}_review.json"
    review_md = output_dir / f"{output_prefix}_review.md"

    candidate_csv = ",".join(candidate_strategy_ids) or "<candidate_ids>"
    baseline_csv = ",".join(baseline_ids) or "<baseline_ids>"
    data_path_text = str(data_path) if data_path is not None else "<data_path>"
    windows_csv = ",".join(windows)

    commands = [
        {
            "step": "standalone_validation",
            "command": " ".join(
                [
                    "python3",
                    "tools/run_long_horizon_portfolio_validation.py",
                    "--manifest-path",
                    str(manifest_path),
                    "--allocation-config-path",
                    str(allocation_config_path),
                    "--allocation-profile",
                    allocation_profile,
                    "--data-path",
                    data_path_text,
                    "--windows",
                    windows_csv,
                    "--strategies",
                    candidate_csv,
                    "--plan-json",
                    str(standalone_json),
                    "--summary-md",
                    str(standalone_md),
                    "--run",
                ]
            ),
            "artifacts": [str(standalone_json), str(standalone_md)],
        },
        {
            "step": "portfolio_evaluate",
            "command": " ".join(
                [
                    "tradectl",
                    "portfolio",
                    "evaluate",
                    "--baseline-strategies",
                    baseline_csv,
                    "--candidate-strategies",
                    candidate_csv,
                    "--data-path",
                    data_path_text,
                    "--windows",
                    windows_csv,
                    "--manifest-path",
                    str(manifest_path),
                    "--allocation-config-path",
                    str(allocation_config_path),
                    "--allocation-profile",
                    allocation_profile,
                    "--output-dir",
                    str(output_dir),
                    "--output-prefix",
                    output_prefix + "_evaluation",
                ]
            ),
            "artifacts": [str(evaluate_json), str(evaluate_md)],
        },
        {
            "step": "standalone_review",
            "command": " ".join(
                [
                    "tradectl",
                    "portfolio",
                    "review",
                    "--summary-json",
                    str(standalone_json),
                    "--output-dir",
                    str(output_dir),
                    "--output-prefix",
                    output_prefix + "_review",
                ]
            ),
            "artifacts": [str(review_json), str(review_md)],
        },
    ]

    runner_command = " ".join(
        [
            "tradectl",
            "portfolio",
            "next-stage",
            "--phase",
            "candidate_onboarding",
            "--manifest-path",
            str(manifest_path),
            "--allocation-config-path",
            str(allocation_config_path),
            "--allocation-profile",
            allocation_profile,
            "--output-dir",
            str(output_dir),
            "--candidate-strategies",
            candidate_csv,
            "--data-path",
            data_path_text,
        ]
        + (
            [
                "--baseline-strategies",
                baseline_csv,
            ]
            if baseline_ids
            else []
        )
    )
    return {
        "status": "ready" if not required_inputs else "pending_inputs",
        "phase": "candidate_onboarding",
        "runbook_ref": DEFAULT_CANDIDATE_RUNBOOK,
        "runner_command": runner_command,
        "required_inputs": required_inputs,
        "baseline_strategy_ids": baseline_ids,
        "candidate_strategy_ids": candidate_strategy_ids,
        "windows": list(windows),
        "commands": commands,
        "artifacts": {
            "standalone_summary_json": str(standalone_json),
            "standalone_summary_md": str(standalone_md),
            "evaluation_summary_json": str(evaluate_json),
            "evaluation_summary_md": str(evaluate_md),
            "review_summary_json": str(review_json),
            "review_summary_md": str(review_md),
        },
    }


def build_multi_pair_preparation_execution_packet(
    *,
    manifest_path: Path,
    allocation_config_path: Path,
    allocation_profile: str,
    data_path: Path | None,
    next_symbol: str | None,
    profile_path: Path,
    data_dir: Path,
    feature_config: Path,
    data_manifest: Path,
    windows: tuple[str, ...] = DEFAULT_MULTI_PAIR_WINDOWS,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    symbol = str(next_symbol or "").strip().upper()
    required_inputs: list[str] = []
    if not symbol:
        required_inputs.append("next_symbol")
    if data_path is None:
        required_inputs.append("data_path")

    output_dir = output_dir or (Path("reports") / "analysis" / "shadow" / "next_stage")
    output_prefix = f"shadow_multi_pair_{symbol.lower() or 'candidate'}"
    validation_json = output_dir / f"{output_prefix}_validation.json"
    validation_md = output_dir / f"{output_prefix}_validation.md"
    candidates_json = output_dir / "portfolio_candidates_snapshot.json"
    admit_json = output_dir / "portfolio_admit_snapshot.json"
    windows_csv = ",".join(windows)
    data_path_text = str(data_path) if data_path is not None else "<data_path>"
    symbol_text = symbol or "<next_symbol>"

    commands = [
        {
            "step": "kernel_validation",
            "command": " ".join(
                [
                    "python3",
                    "tools/run_long_horizon_portfolio_validation.py",
                    "--manifest-path",
                    str(manifest_path),
                    "--allocation-config-path",
                    str(allocation_config_path),
                    "--allocation-profile",
                    allocation_profile,
                    "--data-path",
                    data_path_text,
                    "--windows",
                    windows_csv,
                    "--plan-json",
                    str(validation_json),
                    "--summary-md",
                    str(validation_md),
                    "--run",
                ]
            ),
            "artifacts": [str(validation_json), str(validation_md)],
        },
        {
            "step": "candidate_snapshot",
            "command": " ".join(
                [
                    "tradectl",
                    "portfolio",
                    "candidates",
                    "--symbols",
                    symbol_text,
                    "--profile",
                    str(profile_path),
                    "--data-dir",
                    str(data_dir),
                    "--feature-config",
                    str(feature_config),
                    "--strategy-manifest",
                    str(manifest_path),
                    "--allocation-config",
                    str(allocation_config_path),
                    "--allocation-profile",
                    allocation_profile,
                    "--data-manifest",
                    str(data_manifest),
                    "--output-dir",
                    str(output_dir),
                ]
            ),
            "artifacts": [str(candidates_json)],
        },
        {
            "step": "admission_snapshot",
            "command": " ".join(
                [
                    "tradectl",
                    "portfolio",
                    "admit",
                    "--symbols",
                    symbol_text,
                    "--profile",
                    str(profile_path),
                    "--data-dir",
                    str(data_dir),
                    "--feature-config",
                    str(feature_config),
                    "--strategy-manifest",
                    str(manifest_path),
                    "--allocation-config",
                    str(allocation_config_path),
                    "--allocation-profile",
                    allocation_profile,
                    "--data-manifest",
                    str(data_manifest),
                    "--output-dir",
                    str(output_dir),
                ]
            ),
            "artifacts": [str(admit_json)],
        },
    ]

    runner_command = " ".join(
        [
            "tradectl",
            "portfolio",
            "next-stage",
            "--phase",
            "multi_pair_preparation",
            "--manifest-path",
            str(manifest_path),
            "--allocation-config-path",
            str(allocation_config_path),
            "--allocation-profile",
            allocation_profile,
            "--profile",
            str(profile_path),
            "--data-dir",
            str(data_dir),
            "--feature-config",
            str(feature_config),
            "--data-manifest",
            str(data_manifest),
            "--output-dir",
            str(output_dir),
            "--next-symbol",
            symbol_text,
            "--data-path",
            data_path_text,
        ]
    )
    return {
        "status": "ready" if not required_inputs else "pending_inputs",
        "phase": "multi_pair_preparation",
        "runbook_ref": DEFAULT_MULTI_PAIR_RUNBOOK,
        "runner_command": runner_command,
        "required_inputs": required_inputs,
        "next_symbol": symbol or None,
        "windows": list(windows),
        "commands": commands,
        "artifacts": {
            "validation_summary_json": str(validation_json),
            "validation_summary_md": str(validation_md),
            "candidates_snapshot_json": str(candidates_json),
            "admit_snapshot_json": str(admit_json),
        },
    }


def render_shadow_next_stage_execution_packet_md(packet: Mapping[str, Any]) -> str:
    lines = [
        "# Shadow Next Stage Execution Packet",
        "",
        f"- phase: `{packet.get('phase')}`",
        f"- status: `{packet.get('status')}`",
        f"- runbook_ref: `{packet.get('runbook_ref')}`",
        f"- runner_command: `{packet.get('runner_command')}`",
        "",
        "## Required Inputs",
        "",
    ]
    required_inputs = list(packet.get("required_inputs") or [])
    if required_inputs:
        for item in required_inputs:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.extend(["", "## Commands", ""])
    for row in packet.get("commands", []):
        lines.append(f"- `{row.get('step')}`: `{row.get('command')}`")
    if not packet.get("commands"):
        lines.append("- none")
    lines.extend(["", "## Artifacts", ""])
    artifacts = packet.get("artifacts") or {}
    if isinstance(artifacts, Mapping) and artifacts:
        for key, value in artifacts.items():
            lines.append(f"- {key}: `{value}`")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _resolve_enabled_strategy_ids(manifest_path: Path) -> tuple[str, ...]:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    strategies = payload.get("strategies") or {}
    enabled = [
        strategy_id
        for strategy_id, config in strategies.items()
        if bool((config or {}).get("enabled", True))
    ]
    return tuple(enabled)


__all__ = [
    "DEFAULT_CANDIDATE_RUNBOOK",
    "DEFAULT_MULTI_PAIR_RUNBOOK",
    "DEFAULT_MULTI_PAIR_WINDOWS",
    "DEFAULT_NEXT_STAGE_WINDOWS",
    "build_candidate_onboarding_execution_packet",
    "build_multi_pair_preparation_execution_packet",
    "render_shadow_next_stage_execution_packet_md",
]
