"""Build automation-ready execution packets for qualified shadow next stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.portfolio.candidate_onboarding import (
    DEFAULT_CANDIDATE_ONBOARDING_RUNBOOK,
    DEFAULT_CANDIDATE_ONBOARDING_WINDOWS,
    build_candidate_onboarding_packet,
)
from src.portfolio.multi_pair import (
    choose_default_multi_pair_symbol,
    materialize_multi_pair_data_manifest,
    resolve_curated_merged_path,
    resolve_pair_metadata,
)

import yaml

DEFAULT_NEXT_STAGE_WINDOWS = DEFAULT_CANDIDATE_ONBOARDING_WINDOWS
DEFAULT_MULTI_PAIR_WINDOWS = ("2016_2025", "2022_2025")
DEFAULT_CANDIDATE_RUNBOOK = DEFAULT_CANDIDATE_ONBOARDING_RUNBOOK
DEFAULT_MULTI_PAIR_RUNBOOK = "docs/runbooks/PORTFOLIO-MULTIPAIR-01.md"
DEFAULT_MULTI_PAIR_EXPANSION_RUNBOOK = "docs/runbooks/PORTFOLIO-MULTIPAIR-04.md"


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
    candidate_csv = ",".join(candidate_strategy_ids) or "<candidate_ids>"
    baseline_csv = ",".join(baseline_ids) or "<baseline_ids>"
    data_path_text = str(data_path) if data_path is not None else "<data_path>"
    output_dir = output_dir or (Path("reports") / "analysis" / "shadow" / "next_stage")
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
    return build_candidate_onboarding_packet(
        manifest_path=manifest_path,
        allocation_config_path=allocation_config_path,
        allocation_profile=allocation_profile,
        data_path=data_path,
        candidate_strategy_ids=candidate_strategy_ids,
        baseline_strategy_ids=baseline_ids,
        windows=windows,
        output_dir=output_dir,
        output_prefix="shadow_candidate_onboarding",
        runner_command=runner_command,
        runbook_ref=DEFAULT_CANDIDATE_ONBOARDING_RUNBOOK,
    )


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
    baseline_symbols = ["USDJPY"]
    symbol = choose_default_multi_pair_symbol(
        baseline_symbols=baseline_symbols,
        requested_symbol=next_symbol,
    )
    pair_metadata = resolve_pair_metadata(symbol)
    required_inputs: list[str] = []
    resolved_data_path = data_path
    if resolved_data_path is None:
        try:
            resolved_data_path = resolve_curated_merged_path(symbol=symbol, data_dir=data_dir)
        except FileNotFoundError:
            required_inputs.append("data_path")

    output_dir = output_dir or (Path("reports") / "analysis" / "shadow" / "next_stage")
    output_prefix = f"shadow_multi_pair_{symbol.lower() or 'candidate'}"
    baseline_validation_json = output_dir / f"{output_prefix}_baseline_validation.json"
    baseline_validation_md = output_dir / f"{output_prefix}_baseline_validation.md"
    validation_json = output_dir / f"{output_prefix}_validation.json"
    validation_md = output_dir / f"{output_prefix}_validation.md"
    candidates_json = output_dir / "portfolio_candidates_snapshot.json"
    admit_json = output_dir / "portfolio_admit_snapshot.json"
    effective_data_manifest = output_dir / f"{output_prefix}_data_manifest.json"
    materialized_data_manifest: dict[str, Any] | None = None
    if data_manifest.exists():
        materialized_data_manifest = materialize_multi_pair_data_manifest(
            source_path=data_manifest,
            symbols=baseline_symbols + [symbol],
            output_path=effective_data_manifest,
            data_dir=data_dir,
        )
    windows_csv = ",".join(windows)
    data_path_text = str(resolved_data_path) if resolved_data_path is not None else "<data_path>"
    symbol_text = symbol
    symbol_scope_csv = ",".join(baseline_symbols + [symbol])
    baseline_symbol_scope_csv = ",".join(baseline_symbols)

    commands = [
        {
            "step": "baseline_kernel_validation",
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
                    "--data-manifest-path",
                    str(data_manifest),
                    "--symbols",
                    baseline_symbol_scope_csv,
                    "--windows",
                    windows_csv,
                    "--plan-json",
                    str(baseline_validation_json),
                    "--summary-md",
                    str(baseline_validation_md),
                    "--run",
                ]
            ),
            "artifacts": [str(baseline_validation_json), str(baseline_validation_md)],
        },
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
                    "--data-manifest-path",
                    str(effective_data_manifest if materialized_data_manifest else data_manifest),
                    "--symbols",
                    symbol_scope_csv,
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
                    symbol_scope_csv,
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
                    str(effective_data_manifest if materialized_data_manifest else data_manifest),
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
                    symbol_scope_csv,
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
                    str(effective_data_manifest if materialized_data_manifest else data_manifest),
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
        "baseline_symbols": baseline_symbols,
        "symbol_scope": baseline_symbols + [symbol],
        "next_symbol": symbol or None,
        "pair_metadata": pair_metadata,
        "windows": list(windows),
        "effective_data_manifest": str(effective_data_manifest if materialized_data_manifest else data_manifest),
        "materialized_data_manifest": materialized_data_manifest or {"status": "skipped"},
        "commands": commands,
        "artifacts": {
            "baseline_validation_summary_json": str(baseline_validation_json),
            "baseline_validation_summary_md": str(baseline_validation_md),
            "validation_summary_json": str(validation_json),
            "validation_summary_md": str(validation_md),
            "candidates_snapshot_json": str(candidates_json),
            "admit_snapshot_json": str(admit_json),
        },
    }


def build_multi_pair_expansion_execution_packet(
    *,
    manifest_path: Path,
    allocation_config_path: Path,
    allocation_profile: str,
    current_symbol: str,
    next_symbol: str,
    profile_path: Path,
    data_dir: Path,
    feature_config: Path,
    data_manifest: Path,
    windows: tuple[str, ...] = DEFAULT_MULTI_PAIR_WINDOWS,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    baseline_symbols = ["USDJPY", choose_default_multi_pair_symbol(requested_symbol=current_symbol)]
    symbol = choose_default_multi_pair_symbol(
        baseline_symbols=baseline_symbols,
        requested_symbol=next_symbol,
    )
    current_pair_metadata = resolve_pair_metadata(baseline_symbols[-1])
    next_pair_metadata = resolve_pair_metadata(symbol)
    required_inputs: list[str] = []

    output_dir = output_dir or (Path("reports") / "analysis" / "shadow" / "next_stage")
    output_prefix = f"shadow_multi_pair_expand_{symbol.lower() or 'candidate'}"
    baseline_validation_json = output_dir / f"{output_prefix}_baseline_validation.json"
    baseline_validation_md = output_dir / f"{output_prefix}_baseline_validation.md"
    validation_json = output_dir / f"{output_prefix}_validation.json"
    validation_md = output_dir / f"{output_prefix}_validation.md"
    candidates_json = output_dir / f"{output_prefix}_candidates_snapshot.json"
    admit_json = output_dir / f"{output_prefix}_admit_snapshot.json"
    effective_data_manifest = output_dir / f"{output_prefix}_data_manifest.json"
    materialized_data_manifest: dict[str, Any] | None = None
    if data_manifest.exists():
        materialized_data_manifest = materialize_multi_pair_data_manifest(
            source_path=data_manifest,
            symbols=baseline_symbols + [symbol],
            output_path=effective_data_manifest,
            data_dir=data_dir,
        )
    windows_csv = ",".join(windows)
    symbol_scope_csv = ",".join(baseline_symbols + [symbol])
    baseline_symbol_scope_csv = ",".join(baseline_symbols)

    commands = [
        {
            "step": "baseline_kernel_validation",
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
                    "--data-manifest-path",
                    str(data_manifest),
                    "--symbols",
                    baseline_symbol_scope_csv,
                    "--windows",
                    windows_csv,
                    "--plan-json",
                    str(baseline_validation_json),
                    "--summary-md",
                    str(baseline_validation_md),
                    "--run",
                ]
            ),
            "artifacts": [str(baseline_validation_json), str(baseline_validation_md)],
        },
        {
            "step": "expanded_kernel_validation",
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
                    "--data-manifest-path",
                    str(effective_data_manifest if materialized_data_manifest else data_manifest),
                    "--symbols",
                    symbol_scope_csv,
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
                    symbol_scope_csv,
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
                    str(effective_data_manifest if materialized_data_manifest else data_manifest),
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
                    symbol_scope_csv,
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
                    str(effective_data_manifest if materialized_data_manifest else data_manifest),
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
            "pair-expansion-rollout",
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
            "--current-symbol",
            baseline_symbols[-1],
            "--next-symbol",
            symbol,
        ]
    )
    return {
        "status": "ready" if not required_inputs else "pending_inputs",
        "phase": "multi_pair_expansion",
        "runbook_ref": DEFAULT_MULTI_PAIR_EXPANSION_RUNBOOK,
        "runner_command": runner_command,
        "required_inputs": required_inputs,
        "baseline_symbols": baseline_symbols,
        "symbol_scope": baseline_symbols + [symbol],
        "current_symbol": baseline_symbols[-1],
        "next_symbol": symbol,
        "current_pair_metadata": current_pair_metadata,
        "next_pair_metadata": next_pair_metadata,
        "windows": list(windows),
        "effective_data_manifest": str(effective_data_manifest if materialized_data_manifest else data_manifest),
        "materialized_data_manifest": materialized_data_manifest or {"status": "skipped"},
        "commands": commands,
        "artifacts": {
            "baseline_validation_summary_json": str(baseline_validation_json),
            "baseline_validation_summary_md": str(baseline_validation_md),
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
    "build_multi_pair_expansion_execution_packet",
    "build_multi_pair_preparation_execution_packet",
    "render_shadow_next_stage_execution_packet_md",
]
