"""Evaluate standalone and marginal portfolio contribution for candidate strategies."""

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

VALIDATION_LOG_DIR = PROJECT_ROOT / "reports" / "validation_log"
ANALYSIS_DIR = PROJECT_ROOT / "reports" / "analysis"
RUNNER = PROJECT_ROOT / "tools" / "run_long_horizon_portfolio_validation.py"
DEFAULT_MANIFEST = PROJECT_ROOT / "config" / "strategy_manifest.parallel_portfolio_v2.yaml"
DEFAULT_ALLOCATION = PROJECT_ROOT / "config" / "strategy_allocation.yaml"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _parse_ids(raw: str) -> list[str]:
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def _parse_required_unique_ids(*, raw: str, field_name: str) -> list[str]:
    values = _parse_ids(raw)
    if not values:
        raise ValueError(f"{field_name} must include at least one id")
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise ValueError(f"{field_name} contains duplicates: {', '.join(duplicates)}")
    return values


def _run_validation(
    *,
    strategy_ids: list[str],
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
        "--strategies",
        ",".join(strategy_ids),
        "--plan-json",
        str(plan_json),
        "--summary-md",
        str(summary_md),
        "--run",
    ]
    subprocess.run(command, check=True, cwd=PROJECT_ROOT)
    return json.loads(plan_json.read_text(encoding="utf-8"))


def _result_index(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row.get("window_name")): row for row in payload.get("results", [])}


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


def _compare_window(
    *,
    baseline_row: Mapping[str, Any] | None,
    standalone_row: Mapping[str, Any] | None,
    combo_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    baseline_summary = dict((baseline_row or {}).get("summary", {}))
    standalone_summary = dict((standalone_row or {}).get("summary", {}))
    combo_summary = dict((combo_row or {}).get("summary", {}))
    return {
        "baseline": {
            "summary": baseline_summary,
            "acceptance": dict((baseline_row or {}).get("acceptance", {})),
            "evidence": dict((baseline_row or {}).get("evidence", {})),
        },
        "standalone": {
            "summary": standalone_summary,
            "acceptance": dict((standalone_row or {}).get("acceptance", {})),
            "evidence": dict((standalone_row or {}).get("evidence", {})),
        },
        "combo": {
            "summary": combo_summary,
            "acceptance": dict((combo_row or {}).get("acceptance", {})),
            "evidence": dict((combo_row or {}).get("evidence", {})),
        },
        "delta_vs_baseline": {
            "pf": _delta(combo_summary.get("pf"), baseline_summary.get("pf")),
            "avg_r": _delta(combo_summary.get("avg_r"), baseline_summary.get("avg_r")),
            "trades": _delta(combo_summary.get("trades"), baseline_summary.get("trades")),
            "win_rate": _delta(combo_summary.get("win_rate"), baseline_summary.get("win_rate")),
        },
    }


def build_evaluation_payload(
    *,
    baseline_strategy_ids: list[str],
    candidate_strategy_ids: list[str],
    windows: tuple[str, ...],
    baseline_payload: Mapping[str, Any],
    standalone_payloads: Mapping[str, Mapping[str, Any]],
    combo_payloads: Mapping[str, Mapping[str, Any]],
    run_dir: Path,
) -> dict[str, Any]:
    baseline_index = _result_index(baseline_payload)
    candidates: list[dict[str, Any]] = []
    for strategy_id in candidate_strategy_ids:
        standalone_index = _result_index(standalone_payloads[strategy_id])
        combo_index = _result_index(combo_payloads[strategy_id])
        windows_payload: list[dict[str, Any]] = []
        for window_name in windows:
            windows_payload.append(
                {
                    "window_name": window_name,
                    **_compare_window(
                        baseline_row=baseline_index.get(window_name),
                        standalone_row=standalone_index.get(window_name),
                        combo_row=combo_index.get(window_name),
                    ),
                }
            )
        candidates.append(
            {
                "strategy_id": strategy_id,
                "standalone_plan_json": str(run_dir / f"{strategy_id}.standalone.json"),
                "combo_plan_json": str(run_dir / f"{strategy_id}.combo.json"),
                "windows": windows_payload,
            }
        )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "baseline_strategy_ids": baseline_strategy_ids,
        "candidate_strategy_ids": candidate_strategy_ids,
        "selected_windows": list(windows),
        "baseline_plan_json": str(run_dir / "baseline.json"),
        "candidates": candidates,
    }


def render_summary_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Portfolio Candidate Evaluation",
        "",
        f"- generated_at_utc: `{payload['generated_at_utc']}`",
        f"- baseline_strategy_ids: `{', '.join(payload['baseline_strategy_ids'])}`",
        f"- candidate_strategy_ids: `{', '.join(payload['candidate_strategy_ids'])}`",
        f"- windows: `{', '.join(payload['selected_windows'])}`",
        "",
    ]
    for candidate in payload.get("candidates", []):
        lines.append(f"## Candidate `{candidate['strategy_id']}`")
        lines.append("")
        lines.append("| Window | Standalone PF | Combo PF | Delta PF | Standalone AvgR | Combo AvgR | Delta AvgR |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for row in candidate.get("windows", []):
            standalone = row.get("standalone", {}).get("summary", {})
            combo = row.get("combo", {}).get("summary", {})
            delta = row.get("delta_vs_baseline", {})
            lines.append(
                "| "
                + f"{row['window_name']} | "
                + f"{standalone.get('pf')} | {combo.get('pf')} | {delta.get('pf')} | "
                + f"{standalone.get('avg_r')} | {combo.get('avg_r')} | {delta.get('avg_r')} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate standalone and marginal portfolio contribution for candidate strategies."
    )
    parser.add_argument("--baseline-strategies", required=True, help="Comma-separated baseline strategy ids")
    parser.add_argument("--candidate-strategies", required=True, help="Comma-separated candidate strategy ids")
    parser.add_argument("--data-path", required=True, help="Merged parquet path")
    parser.add_argument("--windows", default="2016_2025,2016_2021", help="Comma-separated window names")
    parser.add_argument("--manifest-path", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--allocation-config-path", default=str(DEFAULT_ALLOCATION))
    parser.add_argument("--allocation-profile", default="portfolio_admission_v2")
    parser.add_argument("--output-prefix", default="portfolio_candidate_evaluation")
    parser.add_argument("--output-json", type=Path, help="Optional explicit summary JSON path")
    parser.add_argument("--output-md", type=Path, help="Optional explicit summary Markdown path")
    args = parser.parse_args()

    baseline_strategy_ids = _parse_required_unique_ids(
        raw=args.baseline_strategies,
        field_name="baseline_strategies",
    )
    candidate_strategy_ids = _parse_required_unique_ids(
        raw=args.candidate_strategies,
        field_name="candidate_strategies",
    )
    windows = tuple(_parse_required_unique_ids(raw=args.windows, field_name="windows"))
    stamp = _utc_stamp()
    run_dir = VALIDATION_LOG_DIR / f"{args.output_prefix}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    baseline_payload = _run_validation(
        strategy_ids=baseline_strategy_ids,
        manifest_path=Path(args.manifest_path),
        allocation_config_path=Path(args.allocation_config_path),
        allocation_profile=args.allocation_profile,
        data_path=Path(args.data_path),
        windows=windows,
        plan_json=run_dir / "baseline.json",
        summary_md=run_dir / "baseline.md",
    )

    standalone_payloads: dict[str, Mapping[str, Any]] = {}
    combo_payloads: dict[str, Mapping[str, Any]] = {}
    for strategy_id in candidate_strategy_ids:
        standalone_payloads[strategy_id] = _run_validation(
            strategy_ids=[strategy_id],
            manifest_path=Path(args.manifest_path),
            allocation_config_path=Path(args.allocation_config_path),
            allocation_profile=args.allocation_profile,
            data_path=Path(args.data_path),
            windows=windows,
            plan_json=run_dir / f"{strategy_id}.standalone.json",
            summary_md=run_dir / f"{strategy_id}.standalone.md",
        )
        combo_payloads[strategy_id] = _run_validation(
            strategy_ids=[*baseline_strategy_ids, strategy_id],
            manifest_path=Path(args.manifest_path),
            allocation_config_path=Path(args.allocation_config_path),
            allocation_profile=args.allocation_profile,
            data_path=Path(args.data_path),
            windows=windows,
            plan_json=run_dir / f"{strategy_id}.combo.json",
            summary_md=run_dir / f"{strategy_id}.combo.md",
        )

    payload = build_evaluation_payload(
        baseline_strategy_ids=baseline_strategy_ids,
        candidate_strategy_ids=candidate_strategy_ids,
        windows=windows,
        baseline_payload=baseline_payload,
        standalone_payloads=standalone_payloads,
        combo_payloads=combo_payloads,
        run_dir=run_dir,
    )
    summary_json = args.output_json or (VALIDATION_LOG_DIR / f"{args.output_prefix}_{stamp}.json")
    summary_md = args.output_md or (ANALYSIS_DIR / f"{args.output_prefix}_{stamp}.md")
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_md.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_md.write_text(render_summary_md(payload), encoding="utf-8")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
