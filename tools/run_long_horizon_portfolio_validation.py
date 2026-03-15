"""Plan and run long-horizon portfolio PoC validations.

This tool is meant to be prepared while historical backfills are still running.
It generates a deterministic validation plan, records basic merged-data quality
stats, and optionally executes `simulate_paper_poc` across long windows.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.paper_poc import simulate_paper_poc
from src.backtest.poc_report import build_poc_report, render_poc_report_md

VALIDATION_LOG_DIR = PROJECT_ROOT / "reports" / "validation_log"
ANALYSIS_DIR = PROJECT_ROOT / "reports" / "analysis"
FEATURE_CONFIG = PROJECT_ROOT / "config" / "feature_pipeline.yaml"
RISK_POLICY = PROJECT_ROOT / "config" / "risk_policy.yaml"
DATA_MANIFEST = PROJECT_ROOT / "reports" / "data_manifest.json"
DEFAULT_MANIFEST = PROJECT_ROOT / "config" / "strategy_manifest.parallel_portfolio_v2.yaml"
DEFAULT_ALLOCATION = PROJECT_ROOT / "config" / "strategy_allocation.yaml"


@dataclass(frozen=True, slots=True)
class FixedAssumptions:
    profile: str = "m1_baseline"
    symbols: tuple[str, ...] = ("USDJPY",)
    spread: float = 0.005
    slippage: float = 0.0015
    slippage_std: float = 0.001
    commission_pct: float = 0.0
    target_r: float = 1.8
    ttl_bars: int = 10
    seed: int = 0


@dataclass(frozen=True, slots=True)
class ValidationWindow:
    name: str
    window_from: str
    window_to: str
    purpose: str


FIXED = FixedAssumptions()

WINDOW_PROFILES: dict[str, tuple[ValidationWindow, ...]] = {
    "usd_jpy_long_horizon": (
        ValidationWindow("2016_2025", "2016-01-01", "2025-12-31", "full_history"),
        ValidationWindow("2016_2021", "2016-01-01", "2021-12-31", "pre_recent_regimes"),
        ValidationWindow("2022_2025", "2022-01-01", "2025-12-31", "recent_regimes"),
        ValidationWindow("2025", "2025-01-01", "2025-12-31", "latest_validation"),
    ),
}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _resolve_latest_merged(symbol: str) -> Path:
    symbol_dir = PROJECT_ROOT / "data" / "research" / "curated" / symbol.lower()
    candidates = sorted(
        symbol_dir.glob(f"{symbol.lower()}_m5_*_merged.parquet"),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        raise FileNotFoundError(f"no merged parquet found under {symbol_dir}")
    return candidates[-1]


def _load_quality_snapshot(path: Path, *, expected_minutes: int) -> dict[str, Any]:
    df = pd.read_parquet(path)
    if "timestamp" not in df.columns:
        raise ValueError(f"timestamp column missing in {path}")
    ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").dropna().sort_values()
    deltas = ts.diff().dropna()
    expected = timedelta(minutes=expected_minutes)
    gap_minutes = [int(delta.total_seconds() // 60) for delta in deltas if delta > expected]
    duplicate_count = int(ts.duplicated().sum())
    return {
        "path": str(path),
        "rows": int(len(df)),
        "start": ts.min().isoformat() if not ts.empty else None,
        "end": ts.max().isoformat() if not ts.empty else None,
        "gap_count": int(len(gap_minutes)),
        "max_gap_minutes": int(max(gap_minutes)) if gap_minutes else 0,
        "duplicate_timestamp_count": duplicate_count,
        "null_counts": {
            col: int(df[col].isna().sum())
            for col in ("open", "high", "low", "close", "volume")
            if col in df.columns
        },
    }


def _run_poc(
    *,
    manifest_path: Path,
    allocation_config_path: Path,
    allocation_profile: str,
    window: ValidationWindow,
    stamp: str,
) -> tuple[Path, Path, Path, dict[str, Any]]:
    result = simulate_paper_poc(
        strategy=None,
        profile=FIXED.profile,
        window_from=window.window_from,
        window_to=window.window_to,
        spread_pips=FIXED.spread,
        slippage_pips=FIXED.slippage,
        slippage_std=FIXED.slippage_std,
        commission_pct=FIXED.commission_pct,
        symbols=list(FIXED.symbols),
        seed=FIXED.seed,
        target_r_multiple=FIXED.target_r,
        ttl_bars=FIXED.ttl_bars,
        risk_policy_path=RISK_POLICY,
        strategy_manifest_path=manifest_path,
        data_manifest_path=DATA_MANIFEST,
        feature_config_path=FEATURE_CONFIG,
        allocation_config_path=allocation_config_path,
        allocation_profile=allocation_profile,
        export_returns=None,
        export_equity=None,
    )
    raw_path = VALIDATION_LOG_DIR / f"long_horizon_portfolio_{stamp}_{window.name}.json"
    report_json_path = ANALYSIS_DIR / f"long_horizon_portfolio_{stamp}_{window.name}_report.json"
    report_md_path = ANALYSIS_DIR / f"long_horizon_portfolio_{stamp}_{window.name}_report.md"
    payload = {
        "strategy": "manifest_hybrid",
        "allocation_profile": allocation_profile,
        "profile": FIXED.profile,
        "seed_used": FIXED.seed,
        "window": {"from": window.window_from, "to": window.window_to},
        "dataset_path": result.dataset_path,
        "dataset_hash": result.dataset_hash,
        "metrics": dict(result.metrics),
        "trades": [trade.as_dict() for trade in result.trades],
    }
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = build_poc_report(raw_path)
    report_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md_path.write_text(render_poc_report_md(report), encoding="utf-8")
    return raw_path, report_json_path, report_md_path, report


def _render_summary_md(payload: Mapping[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Long-Horizon Portfolio Validation")
    lines.append("")
    lines.append(f"- generated_at_utc: `{payload['generated_at_utc']}`")
    lines.append(f"- manifest: `{payload['manifest_path']}`")
    lines.append(f"- allocation_profile: `{payload['allocation_profile']}`")
    lines.append(f"- symbol_scope: `{', '.join(payload['fixed_assumptions']['symbols'])}`")
    lines.append("")

    quality = payload.get("data_quality", {})
    if quality:
        lines.append("## Data Quality")
        lines.append("")
        lines.append(f"- source: `{quality.get('path')}`")
        lines.append(
            f"- rows/start/end: `{quality.get('rows')}` / `{quality.get('start')}` / `{quality.get('end')}`"
        )
        lines.append(
            f"- gaps/max_gap/duplicates: `{quality.get('gap_count')}` / `{quality.get('max_gap_minutes')}` / `{quality.get('duplicate_timestamp_count')}`"
        )
        lines.append("")

    lines.append("## Window Summary")
    lines.append("")
    lines.append("| Window | Purpose | PF | AvgR | MaxDD | Trades | Gate |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | --- |")
    for row in payload.get("results", []):
        summary = row.get("summary", {})
        acceptance = row.get("acceptance", {})
        lines.append(
            "| "
            + f"{row['window_name']} | {row['purpose']} | "
            + f"{summary.get('pf')} | {summary.get('avg_r')} | {summary.get('max_drawdown')} | "
            + f"{summary.get('trades')} | {acceptance.get('status')} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def _build_summary_row(
    *,
    window: ValidationWindow,
    report: dict[str, Any],
    raw_path: Path,
    report_json_path: Path,
    report_md_path: Path,
) -> dict[str, Any]:
    summary = report.get("summary", {})
    metrics = report.get("metrics", {})
    gate = report.get("acceptance_gate", {})
    return {
        "window_name": window.name,
        "purpose": window.purpose,
        "window": {"from": window.window_from, "to": window.window_to},
        "summary": {
            "pf": summary.get("pf"),
            "avg_r": summary.get("avg_r"),
            "win_rate": summary.get("win_rate"),
            "trades": summary.get("count"),
            "max_drawdown": metrics.get("max_drawdown_all"),
        },
        "acceptance": {
            "status": gate.get("status"),
            "checks": gate.get("checks", {}),
        },
        "evidence": {
            "raw": str(raw_path),
            "report_json": str(report_json_path),
            "report_md": str(report_md_path),
        },
    }


def build_plan(
    *,
    manifest_path: Path,
    allocation_config_path: Path,
    allocation_profile: str,
    symbol: str,
    data_path: Path | None,
    expected_minutes: int,
    window_profile: str,
) -> dict[str, Any]:
    merged_path = data_path or _resolve_latest_merged(symbol)
    windows = WINDOW_PROFILES[window_profile]
    quality = _load_quality_snapshot(merged_path, expected_minutes=expected_minutes)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manifest_path": str(manifest_path),
        "allocation_config_path": str(allocation_config_path),
        "allocation_profile": allocation_profile,
        "window_profile": window_profile,
        "fixed_assumptions": asdict(FIXED),
        "data_quality": quality,
        "windows": [asdict(window) for window in windows],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run long-horizon portfolio PoC validations.")
    parser.add_argument(
        "--manifest-path",
        default=str(DEFAULT_MANIFEST),
        help="Combined strategy manifest path",
    )
    parser.add_argument(
        "--allocation-config-path",
        default=str(DEFAULT_ALLOCATION),
        help="Allocation config path",
    )
    parser.add_argument(
        "--allocation-profile",
        default="portfolio_admission_v2",
        help="Allocation profile to validate",
    )
    parser.add_argument("--symbol", default="USDJPY", help="Primary symbol for data quality checks")
    parser.add_argument("--data-path", help="Merged parquet path for quality checks")
    parser.add_argument(
        "--window-profile",
        default="usd_jpy_long_horizon",
        choices=sorted(WINDOW_PROFILES),
        help="Window plan profile",
    )
    parser.add_argument(
        "--expected-minutes",
        type=int,
        default=5,
        help="Expected bar interval for gap checks",
    )
    parser.add_argument("--plan-json", help="Optional JSON output for the plan/summary payload")
    parser.add_argument("--summary-md", help="Optional markdown output for the summary")
    parser.add_argument("--run", action="store_true", help="Execute PoC runs after planning")
    args = parser.parse_args()

    manifest_path = Path(args.manifest_path)
    allocation_config_path = Path(args.allocation_config_path)
    data_path = Path(args.data_path) if args.data_path else None
    payload = build_plan(
        manifest_path=manifest_path,
        allocation_config_path=allocation_config_path,
        allocation_profile=args.allocation_profile,
        symbol=args.symbol.upper(),
        data_path=data_path,
        expected_minutes=args.expected_minutes,
        window_profile=args.window_profile,
    )

    if args.run:
        stamp = _utc_stamp()
        results: list[dict[str, Any]] = []
        for window in WINDOW_PROFILES[args.window_profile]:
            raw_path, report_json_path, report_md_path, report = _run_poc(
                manifest_path=manifest_path,
                allocation_config_path=allocation_config_path,
                allocation_profile=args.allocation_profile,
                window=window,
                stamp=stamp,
            )
            results.append(
                _build_summary_row(
                    window=window,
                    report=report,
                    raw_path=raw_path,
                    report_json_path=report_json_path,
                    report_md_path=report_md_path,
                )
            )
        payload["run_stamp"] = stamp
        payload["results"] = results

    if args.plan_json:
        plan_path = Path(args.plan_json)
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.summary_md:
        summary_path = Path(args.summary_md)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(_render_summary_md(payload), encoding="utf-8")

    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
