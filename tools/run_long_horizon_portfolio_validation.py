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
from typing import Any, Iterable, Mapping

import pandas as pd
import yaml

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


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def _yaml_dump_lines(value: Any, *, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, Mapping):
        if not value:
            return [f"{prefix}{{}}"]
        lines: list[str] = []
        for key, item in value.items():
            key_prefix = f"{prefix}{key}:"
            if isinstance(item, Mapping):
                if item:
                    lines.append(key_prefix)
                    lines.extend(_yaml_dump_lines(item, indent=indent + 2))
                else:
                    lines.append(f"{key_prefix} {{}}")
            elif isinstance(item, (list, tuple)):
                if item:
                    lines.append(key_prefix)
                    lines.extend(_yaml_dump_lines(list(item), indent=indent + 2))
                else:
                    lines.append(f"{key_prefix} []")
            else:
                lines.append(f"{key_prefix} {_yaml_scalar(item)}")
        return lines
    if isinstance(value, (list, tuple)):
        if not value:
            return [f"{prefix}[]"]
        lines = []
        for item in value:
            if isinstance(item, Mapping):
                if item:
                    lines.append(f"{prefix}-")
                    lines.extend(_yaml_dump_lines(item, indent=indent + 2))
                else:
                    lines.append(f"{prefix}- {{}}")
            elif isinstance(item, (list, tuple)):
                if item:
                    lines.append(f"{prefix}-")
                    lines.extend(_yaml_dump_lines(list(item), indent=indent + 2))
                else:
                    lines.append(f"{prefix}- []")
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
        return lines
    return [f"{prefix}{_yaml_scalar(value)}"]


def _yaml_dump_text(payload: Mapping[str, Any]) -> str:
    dumper = getattr(yaml, "safe_dump", None)
    if dumper is not None:
        return dumper(dict(payload), allow_unicode=True, sort_keys=False)
    return "\n".join(_yaml_dump_lines(dict(payload))) + "\n"


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


def _effective_manifest_output_path(*, stamp: str, variant: str) -> Path:
    suffix = {"subset": "focused", "override": "override"}[variant]
    return VALIDATION_LOG_DIR / f"long_horizon_portfolio_{stamp}_effective_manifest.{suffix}.yaml"


def _resolve_windows(
    *,
    window_profile: str,
    selected_names: Iterable[str] | None = None,
) -> tuple[ValidationWindow, ...]:
    windows = WINDOW_PROFILES[window_profile]
    if not selected_names:
        return windows
    selected = {str(name).strip() for name in selected_names if str(name).strip()}
    if not selected:
        return windows
    filtered = tuple(window for window in windows if window.name in selected)
    missing = sorted(selected - {window.name for window in filtered})
    if missing:
        raise ValueError(
            f"unknown windows for profile {window_profile}: {', '.join(missing)}"
        )
    return filtered


def _resolve_strategy_ids(
    *,
    manifest_path: Path,
    selected_ids: Iterable[str] | None = None,
) -> tuple[str, ...]:
    if not selected_ids:
        return ()
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    strategies = payload.get("strategies") or {}
    selected = tuple(str(item).strip() for item in selected_ids if str(item).strip())
    if not selected:
        return ()
    missing = sorted(set(selected) - set(strategies))
    if missing:
        raise ValueError(
            f"unknown strategies for manifest {manifest_path}: {', '.join(missing)}"
        )
    return tuple(strategy_id for strategy_id in strategies if strategy_id in selected)


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def _load_strategy_overrides(path: Path | None) -> dict[str, Mapping[str, Any]]:
    if path is None:
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, Mapping):
        raise ValueError(f"strategy overrides must be a mapping: {path}")
    overrides: dict[str, Mapping[str, Any]] = {}
    for strategy_id, config in payload.items():
        if not isinstance(strategy_id, str) or not strategy_id.strip():
            raise ValueError(f"strategy override key must be a non-empty string: {path}")
        if not isinstance(config, Mapping):
            raise ValueError(f"strategy override for {strategy_id} must be a mapping: {path}")
        overrides[strategy_id.strip()] = config
    return overrides


def _materialize_strategy_subset_manifest(
    *,
    source_manifest_path: Path,
    selected_strategy_ids: Iterable[str],
    strategy_overrides: Mapping[str, Mapping[str, Any]] | None,
    output_path: Path,
) -> Path:
    selected = tuple(selected_strategy_ids)
    if not selected:
        raise ValueError("selected_strategy_ids must not be empty")
    payload = yaml.safe_load(source_manifest_path.read_text(encoding="utf-8")) or {}
    strategies = payload.get("strategies") or {}
    for strategy_id, config in strategies.items():
        strategy_payload = dict(config or {})
        strategy_payload["enabled"] = strategy_id in selected
        override = (strategy_overrides or {}).get(strategy_id)
        if override is not None:
            strategy_payload = _deep_merge(strategy_payload, override)
        strategies[strategy_id] = strategy_payload
    payload["strategies"] = strategies
    payload["manifest_name"] = f"{payload.get('manifest_name', 'Strategy Manifest')} [subset]"
    notes = [str(payload.get("notes", "")).rstrip(), f"Focused validation subset: {', '.join(selected)}"]
    if strategy_overrides:
        notes.append("Focused validation overrides: " + ", ".join(sorted(strategy_overrides)))
    payload["notes"] = "\n".join(part for part in notes if part).strip()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_yaml_dump_text(payload), encoding="utf-8")
    return output_path


def _materialize_override_manifest(
    *,
    source_manifest_path: Path,
    strategy_overrides: Mapping[str, Mapping[str, Any]],
    output_path: Path,
) -> Path:
    if not strategy_overrides:
        raise ValueError("strategy_overrides must not be empty")
    payload = yaml.safe_load(source_manifest_path.read_text(encoding="utf-8")) or {}
    strategies = payload.get("strategies") or {}
    missing = sorted(set(strategy_overrides) - set(strategies))
    if missing:
        raise ValueError(
            f"unknown strategies for manifest {source_manifest_path}: {', '.join(missing)}"
        )
    for strategy_id, override in strategy_overrides.items():
        strategies[strategy_id] = _deep_merge(dict(strategies[strategy_id] or {}), override)
    payload["strategies"] = strategies
    payload["manifest_name"] = f"{payload.get('manifest_name', 'Strategy Manifest')} [override]"
    payload["notes"] = (
        f"{payload.get('notes', '').rstrip()}\nFocused validation overrides: "
        + ", ".join(sorted(strategy_overrides))
    ).strip()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_yaml_dump_text(payload), encoding="utf-8")
    return output_path


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
    symbols: tuple[str, ...],
    data_manifest_path: Path,
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
        symbols=list(symbols),
        seed=FIXED.seed,
        target_r_multiple=FIXED.target_r,
        ttl_bars=FIXED.ttl_bars,
        risk_policy_path=RISK_POLICY,
        strategy_manifest_path=manifest_path,
        data_manifest_path=data_manifest_path,
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
        "symbols": list(symbols),
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
    selected_strategy_ids = payload.get("selected_strategy_ids") or []
    if selected_strategy_ids:
        lines.append(f"- selected_strategy_ids: `{', '.join(selected_strategy_ids)}`")
    strategy_override_ids = payload.get("strategy_override_ids") or []
    if strategy_override_ids:
        lines.append(f"- strategy_override_ids: `{', '.join(strategy_override_ids)}`")
    strategy_overrides_path = payload.get("strategy_overrides_path")
    if strategy_overrides_path:
        lines.append(f"- strategy_overrides_path: `{strategy_overrides_path}`")
    effective_manifest_path = payload.get("effective_manifest_path")
    if effective_manifest_path:
        lines.append(f"- effective_manifest: `{effective_manifest_path}`")
    lines.append(f"- allocation_profile: `{payload['allocation_profile']}`")
    lines.append(f"- symbol_scope: `{', '.join(payload['fixed_assumptions']['symbols'])}`")
    lines.append("")

    quality_by_symbol = payload.get("data_quality_by_symbol")
    if isinstance(quality_by_symbol, Mapping) and quality_by_symbol:
        lines.append("## Data Quality")
        lines.append("")
        for symbol, quality in quality_by_symbol.items():
            lines.append(f"### `{symbol}`")
            lines.append("")
            lines.append(f"- source: `{quality.get('path')}`")
            lines.append(
                f"- rows/start/end: `{quality.get('rows')}` / `{quality.get('start')}` / `{quality.get('end')}`"
            )
            lines.append(
                f"- gaps/max_gap/duplicates: `{quality.get('gap_count')}` / `{quality.get('max_gap_minutes')}` / `{quality.get('duplicate_timestamp_count')}`"
            )
            lines.append("")
    else:
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
            "max_drawdown": metrics.get("max_drawdown", metrics.get("max_drawdown_all")),
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
    symbols: tuple[str, ...] | None = None,
    data_manifest_path: Path = DATA_MANIFEST,
    expected_minutes: int,
    window_profile: str,
    selected_windows: Iterable[str] | None = None,
    selected_strategy_ids: Iterable[str] | None = None,
    strategy_overrides_path: Path | None = None,
) -> dict[str, Any]:
    resolved_symbols = tuple(
        str(item).strip().upper()
        for item in (symbols or (symbol,))
        if str(item).strip()
    ) or (symbol,)
    quality_paths: dict[str, Path] = {}
    for index, item in enumerate(resolved_symbols):
        quality_paths[item] = data_path if index == 0 and data_path is not None else _resolve_latest_merged(item)
    windows = _resolve_windows(window_profile=window_profile, selected_names=selected_windows)
    strategies = _resolve_strategy_ids(
        manifest_path=manifest_path,
        selected_ids=selected_strategy_ids,
    )
    strategy_overrides = _load_strategy_overrides(strategy_overrides_path)
    if strategy_overrides:
        _resolve_strategy_ids(
            manifest_path=manifest_path,
            selected_ids=tuple(strategy_overrides),
        )
    quality_by_symbol = {
        item: _load_quality_snapshot(path, expected_minutes=expected_minutes)
        for item, path in quality_paths.items()
    }
    fixed_assumptions = asdict(FIXED)
    fixed_assumptions["symbols"] = list(resolved_symbols)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manifest_path": str(manifest_path),
        "allocation_config_path": str(allocation_config_path),
        "allocation_profile": allocation_profile,
        "window_profile": window_profile,
        "selected_windows": [window.name for window in windows],
        "selected_strategy_ids": list(strategies),
        "strategy_overrides_path": str(strategy_overrides_path) if strategy_overrides_path else None,
        "strategy_override_ids": sorted(strategy_overrides),
        "fixed_assumptions": fixed_assumptions,
        "data_quality": quality_by_symbol.get(symbol),
        "data_quality_by_symbol": quality_by_symbol,
        "data_manifest_path": str(data_manifest_path),
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
    parser.add_argument("--symbols", help="Comma-separated symbols for the validation run")
    parser.add_argument("--data-path", help="Merged parquet path for quality checks")
    parser.add_argument("--data-manifest-path", default=str(DATA_MANIFEST), help="Data manifest path")
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
    parser.add_argument(
        "--windows",
        help="Comma-separated subset of window names to run/plan (for example: 2016_2021,2016_2025)",
    )
    parser.add_argument(
        "--strategies",
        help="Comma-separated subset of strategy ids to enable for focused validation",
    )
    parser.add_argument(
        "--strategy-overrides-path",
        help="Optional YAML/JSON file with partial strategy config overrides for focused validation",
    )
    parser.add_argument("--plan-json", help="Optional JSON output for the plan/summary payload")
    parser.add_argument("--summary-md", help="Optional markdown output for the summary")
    parser.add_argument("--run", action="store_true", help="Execute PoC runs after planning")
    args = parser.parse_args()

    manifest_path = Path(args.manifest_path)
    allocation_config_path = Path(args.allocation_config_path)
    data_path = Path(args.data_path) if args.data_path else None
    selected_windows = tuple(
        part.strip() for part in str(args.windows or "").split(",") if part.strip()
    )
    selected_strategy_ids = tuple(
        part.strip() for part in str(args.strategies or "").split(",") if part.strip()
    )
    strategy_overrides_path = (
        Path(args.strategy_overrides_path) if args.strategy_overrides_path else None
    )
    payload = build_plan(
        manifest_path=manifest_path,
        allocation_config_path=allocation_config_path,
        allocation_profile=args.allocation_profile,
        symbol=args.symbol.upper(),
        data_path=data_path,
        symbols=tuple(part.strip().upper() for part in str(args.symbols or "").split(",") if part.strip()),
        data_manifest_path=Path(args.data_manifest_path),
        expected_minutes=args.expected_minutes,
        window_profile=args.window_profile,
        selected_windows=selected_windows,
        selected_strategy_ids=selected_strategy_ids,
        strategy_overrides_path=strategy_overrides_path,
    )

    if args.run:
        stamp = _utc_stamp()
        results: list[dict[str, Any]] = []
        effective_manifest_path = manifest_path
        strategy_overrides = _load_strategy_overrides(strategy_overrides_path)
        if selected_strategy_ids:
            effective_manifest_path = _materialize_strategy_subset_manifest(
                source_manifest_path=manifest_path,
                selected_strategy_ids=payload["selected_strategy_ids"],
                strategy_overrides=strategy_overrides,
                output_path=_effective_manifest_output_path(stamp=stamp, variant="subset"),
            )
            payload["effective_manifest_path"] = str(effective_manifest_path)
        elif strategy_overrides:
            effective_manifest_path = _materialize_override_manifest(
                source_manifest_path=manifest_path,
                strategy_overrides=strategy_overrides,
                output_path=_effective_manifest_output_path(stamp=stamp, variant="override"),
            )
            payload["effective_manifest_path"] = str(effective_manifest_path)
        for window in _resolve_windows(
            window_profile=args.window_profile,
            selected_names=selected_windows,
        ):
            raw_path, report_json_path, report_md_path, report = _run_poc(
                manifest_path=effective_manifest_path,
                allocation_config_path=allocation_config_path,
                allocation_profile=args.allocation_profile,
                symbols=tuple(str(item).upper() for item in payload["fixed_assumptions"]["symbols"]),
                data_manifest_path=Path(str(payload["data_manifest_path"])),
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
