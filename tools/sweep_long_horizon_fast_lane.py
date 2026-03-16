"""Run multiple focused long-horizon validation cases and summarize the comparison."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import yaml

from tools.run_long_horizon_portfolio_validation import _yaml_dump_text

VALIDATION_LOG_DIR = PROJECT_ROOT / "reports" / "validation_log"
ANALYSIS_DIR = PROJECT_ROOT / "reports" / "analysis"
RUNNER = PROJECT_ROOT / "tools" / "run_long_horizon_portfolio_validation.py"
DEFAULT_MANIFEST = PROJECT_ROOT / "config" / "strategy_manifest.parallel_portfolio_v2.yaml"
DEFAULT_ALLOCATION = PROJECT_ROOT / "config" / "strategy_allocation.yaml"


@dataclass(frozen=True, slots=True)
class SweepCase:
    case_id: str
    note: str | None
    strategy_overrides: Mapping[str, Any]


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_cases(path: Path) -> list[SweepCase]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(payload, Mapping):
        items = [
            {"case_id": str(case_id), **(config or {})}
            for case_id, config in payload.items()
        ]
    elif isinstance(payload, list):
        items = payload
    else:
        raise ValueError(f"case payload must be a mapping or list: {path}")

    cases: list[SweepCase] = []
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError(f"case entry must be a mapping: {path}")
        case_id = str(item.get("case_id", "")).strip()
        if not case_id:
            raise ValueError(f"case entry missing case_id: {path}")
        overrides = item.get("strategy_overrides") or {}
        if not isinstance(overrides, Mapping):
            raise ValueError(f"strategy_overrides must be a mapping for case {case_id}")
        note = item.get("note")
        cases.append(
            SweepCase(
                case_id=case_id,
                note=str(note).strip() if note is not None and str(note).strip() else None,
                strategy_overrides=overrides,
            )
        )
    return cases


def _render_summary_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Long-Horizon Fast Lane Sweep",
        "",
        f"- generated_at_utc: `{payload['generated_at_utc']}`",
        f"- strategy_id: `{payload['strategy_id']}`",
        f"- windows: `{', '.join(payload['selected_windows'])}`",
        "",
        "## Cases",
        "",
        "| Case | 2016_2025 PF | 2016_2025 AvgR | 2016_2021 PF | 2016_2021 AvgR | Notes |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for case in payload.get("cases", []):
        windows = {item["window_name"]: item for item in case.get("results", [])}
        full = windows.get("2016_2025", {})
        pre = windows.get("2016_2021", {})
        full_summary = full.get("summary", {})
        pre_summary = pre.get("summary", {})
        lines.append(
            "| "
            + f"{case['case_id']} | "
            + f"{full_summary.get('pf')} | {full_summary.get('avg_r')} | "
            + f"{pre_summary.get('pf')} | {pre_summary.get('avg_r')} | "
            + f"{case.get('note') or ''} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def _run_case(
    *,
    case: SweepCase,
    strategy_id: str,
    manifest_path: Path,
    allocation_config_path: Path,
    allocation_profile: str,
    data_path: Path,
    windows: tuple[str, ...],
    run_dir: Path,
) -> dict[str, Any]:
    override_path = run_dir / f"{case.case_id}_override.yaml"
    override_path.write_text(_yaml_dump_text(case.strategy_overrides), encoding="utf-8")
    plan_json = run_dir / f"{case.case_id}.json"
    summary_md = run_dir / f"{case.case_id}.md"
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
        strategy_id,
        "--strategy-overrides-path",
        str(override_path),
        "--plan-json",
        str(plan_json),
        "--summary-md",
        str(summary_md),
        "--run",
    ]
    subprocess.run(command, check=True, cwd=PROJECT_ROOT)
    return json.loads(plan_json.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep focused long-horizon override cases.")
    parser.add_argument("--strategy-id", required=True, help="Strategy id to validate")
    parser.add_argument("--cases-path", required=True, help="YAML/JSON file with sweep cases")
    parser.add_argument("--data-path", required=True, help="Merged parquet path")
    parser.add_argument("--windows", default="2016_2025,2016_2021", help="Comma-separated window names")
    parser.add_argument("--manifest-path", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--allocation-config-path", default=str(DEFAULT_ALLOCATION))
    parser.add_argument("--allocation-profile", default="portfolio_admission_v2")
    parser.add_argument("--output-prefix", default="long_horizon_fast_lane_sweep")
    args = parser.parse_args()

    cases = _load_cases(Path(args.cases_path))
    windows = tuple(part.strip() for part in str(args.windows).split(",") if part.strip())
    stamp = _utc_stamp()
    run_dir = VALIDATION_LOG_DIR / f"{args.output_prefix}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    case_results = [
        _run_case(
            case=case,
            strategy_id=args.strategy_id,
            manifest_path=Path(args.manifest_path),
            allocation_config_path=Path(args.allocation_config_path),
            allocation_profile=args.allocation_profile,
            data_path=Path(args.data_path),
            windows=windows,
            run_dir=run_dir,
        )
        for case in cases
    ]

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "strategy_id": args.strategy_id,
        "selected_windows": list(windows),
        "cases_path": str(args.cases_path),
        "cases": [
            {
                "case_id": case.case_id,
                "note": case.note,
                "strategy_overrides": case.strategy_overrides,
                "results": result.get("results", []),
                "plan_json": str(run_dir / f"{case.case_id}.json"),
                "summary_md": str(run_dir / f"{case.case_id}.md"),
            }
            for case, result in zip(cases, case_results, strict=True)
        ],
    }
    summary_json = VALIDATION_LOG_DIR / f"{args.output_prefix}_{stamp}.json"
    summary_md = ANALYSIS_DIR / f"{args.output_prefix}_{stamp}.md"
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_md.write_text(_render_summary_md(payload), encoding="utf-8")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
