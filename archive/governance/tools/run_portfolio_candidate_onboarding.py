"""Execute or render the canonical baseline candidate-onboarding workflow."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.portfolio.candidate_onboarding import (
    DEFAULT_BASELINE_CANDIDATE_ONBOARDING_RUNBOOK,
    append_candidate_onboarding_promotion_ledger,
    apply_candidate_promotions_to_manifest,
    build_candidate_onboarding_decision_summary,
    build_candidate_onboarding_packet,
    build_candidate_onboarding_promotion_gate_summary,
    materialize_candidate_onboarding_promotion_packet,
    render_candidate_onboarding_packet_md,
)


def _parse_ids(raw: str | None) -> list[str]:
    if raw is None:
        return []
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def _load_json(path: Path | None) -> Mapping[str, Any] | None:
    if path is None or not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, Mapping):
        return payload
    raise ValueError(f"{path} must contain a JSON object")


def run_candidate_onboarding(
    *,
    manifest_path: Path,
    allocation_config_path: Path,
    allocation_profile: str,
    data_path: Path | None,
    candidate_strategies: list[str],
    baseline_strategies: list[str] | None,
    windows: tuple[str, ...],
    output_dir: Path,
    output_prefix: str,
    shadow_ops_json: Path | None = None,
    run: bool = False,
    promote: bool = False,
    runner_command: str | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    packet = build_candidate_onboarding_packet(
        manifest_path=manifest_path,
        allocation_config_path=allocation_config_path,
        allocation_profile=allocation_profile,
        data_path=data_path,
        candidate_strategy_ids=candidate_strategies,
        baseline_strategy_ids=baseline_strategies,
        windows=windows,
        output_dir=output_dir,
        output_prefix=output_prefix,
        runner_command=runner_command,
        runbook_ref=DEFAULT_BASELINE_CANDIDATE_ONBOARDING_RUNBOOK,
    )

    execution_steps: list[dict[str, Any]] = []
    execution_status = "planned"
    if run and str(packet.get("status") or "") == "ready":
        for row in packet.get("commands", []):
            command = str((row or {}).get("command") or "")
            subprocess.run(command, shell=True, check=True, cwd=PROJECT_ROOT)
            execution_steps.append(
                {
                    "step": row.get("step"),
                    "status": "completed",
                    "command": command,
                    "artifacts": list((row or {}).get("artifacts") or []),
                }
            )
        execution_status = "completed"
    elif run:
        execution_status = "blocked_missing_inputs"

    packet["execution_status"] = execution_status
    packet["execution_steps"] = execution_steps

    onboarding_result_summary = build_candidate_onboarding_decision_summary({"packet": packet})
    shadow_ops_summary = _load_json(shadow_ops_json) or {}
    promotion_gate_summary = build_candidate_onboarding_promotion_gate_summary(
        onboarding_result_summary,
        rollout_suppression_summary=shadow_ops_summary.get("rollout_suppression_summary"),
        recovery_execution_state=shadow_ops_summary.get("shadow_feedback_recovery_execution_state"),
        runtime_guardrail_summary=shadow_ops_summary.get("runtime_guardrail_summary"),
    )
    promotion_packet = materialize_candidate_onboarding_promotion_packet(
        packet,
        manifest_path=manifest_path,
        output_dir=output_dir,
        promotion_gate_summary=promotion_gate_summary,
    )

    packet["candidate_onboarding_result_summary"] = onboarding_result_summary
    packet["candidate_onboarding_promotion_gate_summary"] = promotion_gate_summary
    packet["promotion_packet"] = promotion_packet
    packet["candidate_onboarding"]["recommended_action"] = str(
        onboarding_result_summary.get("promotion_next_action") or "review_candidate_onboarding_result"
    )
    packet["eligibility_status"] = str(
        promotion_gate_summary.get("promotion_gate_status") or "review_required"
    )

    promotion_execution: dict[str, Any] | None = None
    if promote and str(promotion_packet.get("status") or "") == "ready":
        manifest_result = apply_candidate_promotions_to_manifest(
            manifest_path=manifest_path,
            promote_strategy_ids=list(promotion_packet.get("promote_strategy_ids") or []),
            output_path=Path(str(promotion_packet.get("manifest_output_path"))),
        )
        promotion_execution = append_candidate_onboarding_promotion_ledger(
            {
                **promotion_packet,
                **manifest_result,
            }
        )

    output_json = output_dir / f"{output_prefix}.json"
    output_md = output_dir / f"{output_prefix}.md"
    output_json.write_text(
        json.dumps(
            {
                "status": "ok",
                "packet": packet,
                "promotion_execution": promotion_execution or {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    output_md.write_text(render_candidate_onboarding_packet_md(packet), encoding="utf-8")
    return {
        "status": "ok",
        "packet": packet,
        "promotion_execution": promotion_execution or {},
        "json_path": str(output_json),
        "markdown_path": str(output_md),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render or run the canonical candidate-onboarding packet.")
    parser.add_argument("--manifest-path", default="config/strategy_manifest.parallel_portfolio_v2.yaml")
    parser.add_argument("--allocation-config-path", default="config/strategy_allocation.yaml")
    parser.add_argument("--allocation-profile", default="portfolio_admission_v2")
    parser.add_argument("--data-path", type=Path)
    parser.add_argument("--candidate-strategies", required=True)
    parser.add_argument("--baseline-strategies")
    parser.add_argument("--windows", default="2016_2021,2016_2025,2022_2025")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports" / "analysis" / "shadow" / "candidate_onboarding")
    parser.add_argument("--output-prefix", default="portfolio_candidate_onboarding")
    parser.add_argument("--shadow-ops-json", type=Path)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args()

    payload = run_candidate_onboarding(
        manifest_path=Path(args.manifest_path),
        allocation_config_path=Path(args.allocation_config_path),
        allocation_profile=str(args.allocation_profile),
        data_path=args.data_path,
        candidate_strategies=_parse_ids(args.candidate_strategies),
        baseline_strategies=_parse_ids(args.baseline_strategies),
        windows=tuple(part.strip() for part in str(args.windows).split(",") if part.strip()),
        output_dir=args.output_dir,
        output_prefix=str(args.output_prefix),
        shadow_ops_json=args.shadow_ops_json,
        run=bool(args.run),
        promote=bool(args.promote),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
