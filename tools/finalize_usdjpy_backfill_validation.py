"""Finalize USDJPY historical backfill and trigger long-horizon validation.

This is a post-backfill orchestrator:
1. Check whether the merged history now reaches the desired target start date.
2. Refresh merged/latest/data_manifest from curated chunk files.
3. Emit a gap report for the refreshed merged file.
4. Run the long-horizon portfolio validation harness.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.dukascopy_backfill_history import load_merged_start_date, resolve_existing_merged


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    status: str
    symbol: str
    target_start: str
    merged_path: str
    merged_start: str
    ready: bool


def assess_backfill_readiness(*, symbol: str, target_start: date, merged_path: Path) -> ReadinessResult:
    merged_start = load_merged_start_date(merged_path)
    ready = merged_start <= target_start
    return ReadinessResult(
        status="ready" if ready else "pending_backfill",
        symbol=symbol,
        target_start=target_start.isoformat(),
        merged_path=str(merged_path.resolve()),
        merged_start=merged_start.isoformat(),
        ready=ready,
    )


def build_merge_command(
    *,
    symbol: str,
    source_dir: Path,
    latest_days: int,
    gap_report: Path | None,
) -> list[str]:
    cmd = [
        sys.executable,
        "tools/update_market_data.py",
        "--symbol",
        symbol,
        "--source-dir",
        str(source_dir),
        "--write-latest",
        "--latest-days",
        str(latest_days),
        "--update-manifest",
    ]
    if gap_report is not None:
        cmd.extend(["--gap-report", str(gap_report), "--gap-minutes", "5", "--gap-exclude-weekend"])
    return cmd


def build_validation_command(
    *,
    manifest_path: Path,
    allocation_config_path: Path,
    allocation_profile: str,
    data_path: Path,
    plan_json: Path,
    summary_md: Path,
) -> list[str]:
    return [
        sys.executable,
        "tools/run_long_horizon_portfolio_validation.py",
        "--manifest-path",
        str(manifest_path),
        "--allocation-config-path",
        str(allocation_config_path),
        "--allocation-profile",
        allocation_profile,
        "--data-path",
        str(data_path),
        "--plan-json",
        str(plan_json),
        "--summary-md",
        str(summary_md),
        "--run",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Finalize USDJPY backfill and run long-horizon portfolio validation."
    )
    parser.add_argument("--symbol", default="USDJPY")
    parser.add_argument("--target-start", default="2016-01-01")
    parser.add_argument("--existing-merged", help="Optional explicit merged parquet path")
    parser.add_argument(
        "--source-dir",
        default=str(PROJECT_ROOT / "data" / "research" / "curated" / "usdjpy"),
        help="Curated source directory to merge from",
    )
    parser.add_argument("--latest-days", type=int, default=120)
    parser.add_argument(
        "--manifest-path",
        default=str(PROJECT_ROOT / "config" / "strategy_manifest.parallel_portfolio_v2.yaml"),
    )
    parser.add_argument(
        "--allocation-config-path",
        default=str(PROJECT_ROOT / "config" / "strategy_allocation.yaml"),
    )
    parser.add_argument("--allocation-profile", default="portfolio_admission_v2")
    parser.add_argument(
        "--plan-json",
        default=str(PROJECT_ROOT / "reports" / "validation_log" / "usdjpy_long_horizon_validation_post_backfill.json"),
    )
    parser.add_argument(
        "--summary-md",
        default=str(PROJECT_ROOT / "reports" / "analysis" / "usdjpy_long_horizon_validation_post_backfill.md"),
    )
    parser.add_argument(
        "--gap-report",
        default=str(PROJECT_ROOT / "reports" / "validation_log" / "usdjpy_post_backfill_gap_report.json"),
    )
    parser.add_argument("--run", action="store_true", help="Execute merge + validation when ready")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run merge/validation even if merged start has not yet reached target_start",
    )
    args = parser.parse_args()

    symbol = args.symbol.upper().strip()
    target_start = date.fromisoformat(args.target_start)
    merged_path = resolve_existing_merged(
        symbol,
        Path(args.existing_merged) if args.existing_merged else None,
    )
    readiness = assess_backfill_readiness(
        symbol=symbol,
        target_start=target_start,
        merged_path=merged_path,
    )
    payload: dict[str, object] = {"readiness": asdict(readiness)}

    if args.run and (readiness.ready or args.force):
        source_dir = Path(args.source_dir)
        gap_report = Path(args.gap_report)
        merge_cmd = build_merge_command(
            symbol=symbol,
            source_dir=source_dir,
            latest_days=args.latest_days,
            gap_report=gap_report,
        )
        subprocess.run(merge_cmd, check=True, cwd=PROJECT_ROOT)
        refreshed_merged = resolve_existing_merged(symbol)
        validation_cmd = build_validation_command(
            manifest_path=Path(args.manifest_path),
            allocation_config_path=Path(args.allocation_config_path),
            allocation_profile=args.allocation_profile,
            data_path=refreshed_merged,
            plan_json=Path(args.plan_json),
            summary_md=Path(args.summary_md),
        )
        subprocess.run(validation_cmd, check=True, cwd=PROJECT_ROOT)
        payload["merge_command"] = merge_cmd
        payload["validation_command"] = validation_cmd
        payload["refreshed_merged"] = str(refreshed_merged.resolve())
    elif args.run:
        payload["status"] = "skipped_not_ready"

    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
