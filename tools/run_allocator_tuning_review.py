"""Generate allocator tuning cases from winner review and validate them."""

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

import yaml

from src.portfolio.allocation_review import (
    apply_allocation_profile_overrides,
    build_allocator_tuning_cases,
    load_allocation_config_payload,
)
from src.portfolio.shadow_feedback import build_shadow_feedback_validation_case, load_shadow_feedback_override_packet
from src.portfolio.shadow_feedback import build_shadow_feedback_validation_case
from tools.run_long_horizon_portfolio_validation import _yaml_dump_text

VALIDATION_LOG_DIR = PROJECT_ROOT / "reports" / "validation_log"
ANALYSIS_DIR = PROJECT_ROOT / "reports" / "analysis"
RUNNER = PROJECT_ROOT / "tools" / "run_long_horizon_portfolio_validation.py"
DEFAULT_MANIFEST = PROJECT_ROOT / "config" / "strategy_manifest.parallel_portfolio_v2.yaml"
DEFAULT_ALLOCATION = PROJECT_ROOT / "config" / "strategy_allocation.yaml"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(after: Any, before: Any) -> float | None:
    after_v = _safe_float(after)
    before_v = _safe_float(before)
    if after_v is None or before_v is None:
        return None
    return round(after_v - before_v, 4)


def _result_index(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row.get("window_name")): row for row in payload.get("results", [])}


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


def _compare_window(
    *,
    baseline_row: Mapping[str, Any] | None,
    case_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    baseline_summary = dict((baseline_row or {}).get("summary", {}))
    case_summary = dict((case_row or {}).get("summary", {}))
    return {
        "baseline": {
            "summary": baseline_summary,
            "acceptance": dict((baseline_row or {}).get("acceptance", {})),
            "evidence": dict((baseline_row or {}).get("evidence", {})),
        },
        "case": {
            "summary": case_summary,
            "acceptance": dict((case_row or {}).get("acceptance", {})),
            "evidence": dict((case_row or {}).get("evidence", {})),
        },
        "delta_vs_baseline": {
            "pf": _delta(case_summary.get("pf"), baseline_summary.get("pf")),
            "avg_r": _delta(case_summary.get("avg_r"), baseline_summary.get("avg_r")),
            "trades": _delta(case_summary.get("trades"), baseline_summary.get("trades")),
            "win_rate": _delta(case_summary.get("win_rate"), baseline_summary.get("win_rate")),
            "max_drawdown": _delta(
                case_summary.get("max_drawdown"),
                baseline_summary.get("max_drawdown"),
            ),
        },
    }


def build_summary_payload(
    *,
    allocation_summary_json: Path,
    selected_windows: tuple[str, ...],
    generated_cases: list[Mapping[str, Any]],
    baseline_payload: Mapping[str, Any],
    case_payloads: Mapping[str, Mapping[str, Any]],
    run_dir: Path,
) -> dict[str, Any]:
    baseline_index = _result_index(baseline_payload)
    cases: list[dict[str, Any]] = []
    for case in generated_cases:
        case_id = str(case["case_id"])
        case_index = _result_index(case_payloads[case_id])
        cases.append(
            {
                "case_id": case_id,
                "note": case.get("note"),
                "source_hypothesis": case.get("source_hypothesis"),
                "allocation_profile_overrides": case.get("allocation_profile_overrides", {}),
                "allocation_config_path": str(run_dir / f"{case_id}.allocation.yaml"),
                "plan_json": str(run_dir / f"{case_id}.json"),
                "summary_md": str(run_dir / f"{case_id}.md"),
                "windows": [
                    {
                        "window_name": window_name,
                        **_compare_window(
                            baseline_row=baseline_index.get(window_name),
                            case_row=case_index.get(window_name),
                        ),
                    }
                    for window_name in selected_windows
                ],
            }
        )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "allocation_summary_json": str(allocation_summary_json),
        "selected_windows": list(selected_windows),
        "baseline_plan_json": str(run_dir / "baseline.json"),
        "cases": cases,
    }


def render_summary_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Allocator Tuning Review",
        "",
        f"- generated_at_utc: `{payload['generated_at_utc']}`",
        f"- allocation_summary_json: `{payload['allocation_summary_json']}`",
        f"- windows: `{', '.join(payload['selected_windows'])}`",
        "",
        "| Case | 2016_2021 PF | Delta PF | 2016_2025 PF | Delta PF | Action |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for case in payload.get("cases", []):
        windows = {item["window_name"]: item for item in case.get("windows", [])}
        pre = windows.get("2016_2021", {})
        full = windows.get("2016_2025", {})
        pre_case = pre.get("case", {}).get("summary", {})
        pre_delta = pre.get("delta_vs_baseline", {})
        full_case = full.get("case", {}).get("summary", {})
        full_delta = full.get("delta_vs_baseline", {})
        action = (case.get("source_hypothesis") or {}).get("suggested_action")
        lines.append(
            "| "
            + f"{case['case_id']} | "
            + f"{pre_case.get('pf')} | {pre_delta.get('pf')} | "
            + f"{full_case.get('pf')} | {full_delta.get('pf')} | "
            + f"{action or ''} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate allocator tuning cases from winner review and run focused validation."
    )
    parser.add_argument("--allocation-summary-json", required=True, type=Path)
    parser.add_argument("--data-path", required=True, type=Path)
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--allocation-config-path", type=Path, default=DEFAULT_ALLOCATION)
    parser.add_argument("--allocation-profile", default="portfolio_admission_v2")
    parser.add_argument(
        "--shadow-feedback-json",
        type=Path,
        help="Optional materialized shadow feedback packet to validate directly.",
    )
    parser.add_argument("--windows", default="2016_2021,2016_2025")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--shadow-feedback-json", type=Path)
    parser.add_argument("--output-prefix", default="allocator_tuning_review")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--run", action="store_true", help="Execute focused validation runs")
    args = parser.parse_args()

    selected_windows = tuple(part.strip() for part in str(args.windows).split(",") if part.strip())
    allocation_payload = load_allocation_config_payload(args.allocation_config_path)
    if allocation_payload is None:
        raise SystemExit(f"could not load allocation config: {args.allocation_config_path}")

    generated_cases = build_allocator_tuning_cases(
        args.allocation_summary_json,
        allocation_config_payload_or_path=allocation_payload,
        allocation_profile=args.allocation_profile,
        limit=args.limit,
    )
    if args.shadow_feedback_json is not None:
        feedback_case = build_shadow_feedback_validation_case(
            load_shadow_feedback_override_packet(args.shadow_feedback_json),
            case_id="shadow_feedback_override_packet",
        )
        if feedback_case is not None:
            generated_cases = [feedback_case, *generated_cases]
    shadow_feedback_case = build_shadow_feedback_validation_case(args.shadow_feedback_json)
    if shadow_feedback_case is not None:
        generated_cases = [shadow_feedback_case, *generated_cases]
    stamp = _utc_stamp()
    run_dir = VALIDATION_LOG_DIR / f"{args.output_prefix}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    baseline_config_path = run_dir / "baseline.allocation.yaml"
    baseline_config_path.write_text(_yaml_dump_text(allocation_payload), encoding="utf-8")

    if not args.run:
        payload = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "allocation_summary_json": str(args.allocation_summary_json),
            "selected_windows": list(selected_windows),
            "baseline_allocation_config_path": str(baseline_config_path),
            "cases": generated_cases,
        }
        summary_json = args.output_json or (VALIDATION_LOG_DIR / f"{args.output_prefix}_{stamp}.json")
        summary_md = args.output_md or (ANALYSIS_DIR / f"{args.output_prefix}_{stamp}.md")
        summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_md.write_text(render_summary_md({"cases": [], **payload}), encoding="utf-8")
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return 0

    baseline_payload = _run_validation(
        manifest_path=args.manifest_path,
        allocation_config_path=baseline_config_path,
        allocation_profile=args.allocation_profile,
        data_path=args.data_path,
        windows=selected_windows,
        plan_json=run_dir / "baseline.json",
        summary_md=run_dir / "baseline.md",
    )

    case_payloads: dict[str, Mapping[str, Any]] = {}
    for case in generated_cases:
        case_id = str(case["case_id"])
        case_config = apply_allocation_profile_overrides(
            allocation_payload,
            allocation_profile=args.allocation_profile,
            overrides=case.get("allocation_profile_overrides", {}),
        )
        case_config_path = run_dir / f"{case_id}.allocation.yaml"
        case_config_path.write_text(_yaml_dump_text(case_config), encoding="utf-8")
        case_payloads[case_id] = _run_validation(
            manifest_path=args.manifest_path,
            allocation_config_path=case_config_path,
            allocation_profile=args.allocation_profile,
            data_path=args.data_path,
            windows=selected_windows,
            plan_json=run_dir / f"{case_id}.json",
            summary_md=run_dir / f"{case_id}.md",
        )

    payload = build_summary_payload(
        allocation_summary_json=args.allocation_summary_json,
        selected_windows=selected_windows,
        generated_cases=generated_cases,
        baseline_payload=baseline_payload,
        case_payloads=case_payloads,
        run_dir=run_dir,
    )
    summary_json = args.output_json or (VALIDATION_LOG_DIR / f"{args.output_prefix}_{stamp}.json")
    summary_md = args.output_md or (ANALYSIS_DIR / f"{args.output_prefix}_{stamp}.md")
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_md.write_text(render_summary_md(payload), encoding="utf-8")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
