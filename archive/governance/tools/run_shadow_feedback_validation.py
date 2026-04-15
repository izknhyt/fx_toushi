"""Run focused validation directly from a shadow feedback override packet."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.portfolio.allocation_review import load_allocation_config_payload
from src.portfolio.shadow_feedback import (
    DEFAULT_ALLOCATION_CONFIG_PATH,
    DEFAULT_ALLOCATION_PROFILE,
    apply_shadow_feedback_override_packet,
    build_shadow_feedback_runtime_guardrail_state,
    build_shadow_feedback_validation_decision,
    load_shadow_feedback_override_packet,
    materialize_shadow_feedback_override_packet,
)
from src.portfolio.shadow_feedback_validation import resolve_shadow_feedback_focused_windows
from tools.run_allocator_tuning_review import _compare_window, _result_index
from tools.run_long_horizon_portfolio_validation import _yaml_dump_text

RUNNER = PROJECT_ROOT / "tools" / "run_long_horizon_portfolio_validation.py"
VALIDATION_LOG_DIR = PROJECT_ROOT / "reports" / "validation_log"
ANALYSIS_DIR = PROJECT_ROOT / "reports" / "analysis"
DEFAULT_MANIFEST = PROJECT_ROOT / "config" / "strategy_manifest.parallel_portfolio_v2.yaml"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _run_validation(
    *,
    manifest_path: Path,
    allocation_config_path: Path,
    allocation_profile: str,
    data_path: Path,
    windows: tuple[str, ...],
    plan_json: Path,
    summary_md: Path,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(RUNNER),
        "--manifest-path",
        str(manifest_path),
        "--allocation-config-path",
        str(allocation_config_path),
        "--allocation-profile",
        allocation_profile,
        "--data-path",
        str(data_path),
        "--windows",
        ",".join(windows),
        "--plan-json",
        str(plan_json),
        "--summary-md",
        str(summary_md),
        "--run",
    ]
    subprocess.run(command, check=True, cwd=PROJECT_ROOT)
    return json.loads(plan_json.read_text(encoding="utf-8"))


def _load_packet(
    *,
    shadow_review_json: Path | None,
    shadow_ops_json: Path | None,
    override_packet_json: Path | None,
    allocation_config_path: Path,
    allocation_profile: str,
) -> dict[str, Any]:
    if override_packet_json is not None:
        return load_shadow_feedback_override_packet(override_packet_json)
    if shadow_ops_json is not None:
        payload = json.loads(shadow_ops_json.read_text(encoding="utf-8"))
        ops_summary = dict(payload.get("ops_summary") or payload)
        packet = ops_summary.get("shadow_feedback_override_packet")
        if isinstance(packet, Mapping):
            return dict(packet)
    if shadow_review_json is not None:
        payload = json.loads(shadow_review_json.read_text(encoding="utf-8"))
        review_summary = dict(payload.get("summary") or payload)
        feedback = review_summary.get("shadow_feedback_summary")
        if isinstance(feedback, Mapping):
            return materialize_shadow_feedback_override_packet(
                feedback,
                allocation_config_payload_or_path=allocation_config_path,
                allocation_profile=allocation_profile,
            )
    return {}


def render_summary_md(payload: Mapping[str, Any]) -> str:
    validation_decision = dict(payload.get("validation_decision") or {})
    runtime_state = dict(payload.get("runtime_guardrail_state") or {})
    lines = [
        "# Shadow Feedback Validation",
        "",
        f"- generated_at_utc: `{payload.get('generated_at_utc')}`",
        f"- packet_status: `{(payload.get('override_packet') or {}).get('status')}`",
        f"- decision: `{validation_decision.get('decision')}`",
        f"- runtime_guardrail_status: `{runtime_state.get('status')}`",
        f"- runtime_guardrail_path: `{payload.get('runtime_guardrail_path') or ''}`",
        "",
        "## Reasons",
        "",
    ]
    for item in validation_decision.get("reasons", []):
        lines.append(f"- {item}")
    if not validation_decision.get("reasons"):
        lines.append("- none")
    lines.extend(["", "## Window Comparison", ""])
    for row in payload.get("windows", []):
        delta = row.get("delta_vs_baseline") or {}
        lines.append(
            f"- {row.get('window_name')}: pf_delta={delta.get('pf')} "
            f"avg_r_delta={delta.get('avg_r')} max_dd_delta={delta.get('max_drawdown')}"
        )
    if not payload.get("windows"):
        lines.append("- none")
    lines.extend(["", "## Runtime Guardrail", ""])
    for key, value in runtime_state.items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a materialized shadow feedback override packet.")
    parser.add_argument("--shadow-review-json", type=Path)
    parser.add_argument("--shadow-ops-json", type=Path)
    parser.add_argument("--override-packet-json", type=Path)
    parser.add_argument("--data-path", type=Path, required=True)
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--allocation-config-path", type=Path, default=DEFAULT_ALLOCATION_CONFIG_PATH)
    parser.add_argument("--allocation-profile", default=DEFAULT_ALLOCATION_PROFILE)
    parser.add_argument("--windows", default="2016_2021,2016_2025")
    parser.add_argument("--output-prefix", default="shadow_feedback_validation")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--runtime-guardrail-path", type=Path)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()

    if not any((args.shadow_review_json, args.shadow_ops_json, args.override_packet_json)):
        raise SystemExit("provide --shadow-review-json, --shadow-ops-json, or --override-packet-json")

    packet = _load_packet(
        shadow_review_json=args.shadow_review_json,
        shadow_ops_json=args.shadow_ops_json,
        override_packet_json=args.override_packet_json,
        allocation_config_path=args.allocation_config_path,
        allocation_profile=args.allocation_profile,
    )
    windows = resolve_shadow_feedback_focused_windows(
        packet,
        fallback_windows=tuple(part.strip() for part in str(args.windows).split(",") if part.strip()),
    )
    config_payload = load_allocation_config_payload(args.allocation_config_path)
    if config_payload is None:
        raise SystemExit(f"could not load allocation config: {args.allocation_config_path}")

    stamp = _utc_stamp()
    run_dir = VALIDATION_LOG_DIR / f"{args.output_prefix}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    baseline_config_path = run_dir / "baseline.allocation.yaml"
    baseline_config_path.write_text(_yaml_dump_text(config_payload), encoding="utf-8")
    override_config = apply_shadow_feedback_override_packet(
        config_payload,
        override_packet_or_path=packet,
        allocation_profile=args.allocation_profile,
    ) or config_payload
    override_config_path = run_dir / "override.allocation.yaml"
    override_config_path.write_text(_yaml_dump_text(override_config), encoding="utf-8")

    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "override_packet": packet,
        "allocation_profile": args.allocation_profile,
        "baseline_allocation_config_path": str(baseline_config_path),
        "override_allocation_config_path": str(override_config_path),
        "windows_requested": list(windows),
    }
    if not args.run:
        summary_json = args.output_json or (VALIDATION_LOG_DIR / f"{args.output_prefix}_{stamp}.json")
        summary_md = args.output_md or (ANALYSIS_DIR / f"{args.output_prefix}_{stamp}.md")
        summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_md.write_text(render_summary_md(payload), encoding="utf-8")
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return 0

    baseline_payload = _run_validation(
        manifest_path=args.manifest_path,
        allocation_config_path=baseline_config_path,
        allocation_profile=args.allocation_profile,
        data_path=args.data_path,
        windows=windows,
        plan_json=run_dir / "baseline.json",
        summary_md=run_dir / "baseline.md",
    )
    override_payload = _run_validation(
        manifest_path=args.manifest_path,
        allocation_config_path=override_config_path,
        allocation_profile=args.allocation_profile,
        data_path=args.data_path,
        windows=windows,
        plan_json=run_dir / "override.json",
        summary_md=run_dir / "override.md",
    )
    baseline_index = _result_index(baseline_payload)
    override_index = _result_index(override_payload)
    windows_payload = [
        {
            "window_name": window_name,
            **_compare_window(
                baseline_row=baseline_index.get(window_name),
                case_row=override_index.get(window_name),
            ),
        }
        for window_name in windows
    ]
    validation_decision = build_shadow_feedback_validation_decision(
        packet,
        baseline_results=baseline_index,
        candidate_results=override_index,
    )
    runtime_guardrail_state = build_shadow_feedback_runtime_guardrail_state(
        packet,
        validation_decision=validation_decision,
    )
    if args.runtime_guardrail_path is not None and runtime_guardrail_state.get("status") == "active":
        args.runtime_guardrail_path.parent.mkdir(parents=True, exist_ok=True)
        args.runtime_guardrail_path.write_text(
            json.dumps(runtime_guardrail_state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    payload.update(
        {
            "baseline_plan_json": str(run_dir / "baseline.json"),
            "override_plan_json": str(run_dir / "override.json"),
            "windows": windows_payload,
            "validation_decision": validation_decision,
            "runtime_guardrail_state": runtime_guardrail_state,
            "runtime_guardrail_path": str(args.runtime_guardrail_path) if args.runtime_guardrail_path else "",
        }
    )
    summary_json = args.output_json or (VALIDATION_LOG_DIR / f"{args.output_prefix}_{stamp}.json")
    summary_md = args.output_md or (ANALYSIS_DIR / f"{args.output_prefix}_{stamp}.md")
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_md.write_text(render_summary_md(payload), encoding="utf-8")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
