"""Regenerate fixed-assumption PoC registry across built-in M1 strategies."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.paper_poc import simulate_paper_poc
from src.backtest.poc_report import build_poc_report, render_poc_report_md

VALIDATION_LOG_DIR = PROJECT_ROOT / "reports" / "validation_log"
ANALYSIS_DIR = PROJECT_ROOT / "reports" / "analysis"
DATA_MANIFEST = PROJECT_ROOT / "reports" / "data_manifest.json"
FEATURE_CONFIG = PROJECT_ROOT / "config" / "feature_pipeline.yaml"
RISK_POLICY = PROJECT_ROOT / "config" / "risk_policy.yaml"


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
class StrategyReviewConfig:
    strategy_id: str
    manifest_path: Path
    lifecycle: str
    notes: tuple[str, ...] = ()


FIXED = FixedAssumptions()

STRATEGY_CONFIGS: tuple[StrategyReviewConfig, ...] = (
    StrategyReviewConfig(
        strategy_id="m1_asia_compression_expansion_breakout",
        manifest_path=PROJECT_ROOT / "config" / "strategy_manifest.asia_compression_expansion_production.yaml",
        lifecycle="production_candidate",
        notes=("Production candidate with atr_min=0.155.",),
    ),
    StrategyReviewConfig(
        strategy_id="m1_baseline_donchian",
        manifest_path=PROJECT_ROOT / "config" / "strategy_manifest.yaml",
        lifecycle="baseline",
    ),
    StrategyReviewConfig(
        strategy_id="m1_baseline_donchian_long_only",
        manifest_path=PROJECT_ROOT / "config" / "strategy_manifest.yaml",
        lifecycle="baseline",
    ),
    StrategyReviewConfig(
        strategy_id="m1_baseline_donchian_upper_only",
        manifest_path=PROJECT_ROOT / "config" / "strategy_manifest.yaml",
        lifecycle="baseline",
    ),
    StrategyReviewConfig(
        strategy_id="m1_baseline_ma_rsi",
        manifest_path=PROJECT_ROOT / "config" / "strategy_manifest.yaml",
        lifecycle="baseline",
    ),
    StrategyReviewConfig(
        strategy_id="m1_us_orb_vwap_retest",
        manifest_path=PROJECT_ROOT / "config" / "strategy_manifest.orb_vwap_experiment.yaml",
        lifecycle="research_only",
        notes=("Research-only strategy; review keeps isolated evidence current.",),
    ),
    StrategyReviewConfig(
        strategy_id="m1_us_session_trend_pullback",
        manifest_path=PROJECT_ROOT / "config" / "strategy_manifest.hybrid_us_experiment.yaml",
        lifecycle="satellite_candidate",
    ),
)

WINDOWS: tuple[tuple[str, str, str], ...] = (
    ("2025", "2025-01-01", "2025-12-31"),
    ("2022_2025", "2022-01-01", "2025-12-31"),
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_poc(
    *,
    cfg: StrategyReviewConfig,
    window_name: str,
    window_from: str,
    window_to: str,
    stamp: str,
) -> tuple[Path, Path, Path]:
    result = simulate_paper_poc(
        strategy=cfg.strategy_id,
        profile=FIXED.profile,
        window_from=window_from,
        window_to=window_to,
        spread_pips=FIXED.spread,
        slippage_pips=FIXED.slippage,
        slippage_std=FIXED.slippage_std,
        commission_pct=FIXED.commission_pct,
        symbols=list(FIXED.symbols),
        seed=FIXED.seed,
        target_r_multiple=FIXED.target_r,
        ttl_bars=FIXED.ttl_bars,
        risk_policy_path=RISK_POLICY,
        strategy_manifest_path=cfg.manifest_path,
        data_manifest_path=DATA_MANIFEST,
        feature_config_path=FEATURE_CONFIG,
        export_returns=None,
        export_equity=None,
    )
    raw_path = (
        VALIDATION_LOG_DIR / f"strategy_registry_{stamp}_{cfg.strategy_id}_{window_name}.json"
    )
    report_json_path = (
        ANALYSIS_DIR / f"strategy_registry_{stamp}_{cfg.strategy_id}_{window_name}_report.json"
    )
    report_md_path = (
        ANALYSIS_DIR / f"strategy_registry_{stamp}_{cfg.strategy_id}_{window_name}_report.md"
    )
    payload = {
        "strategy": cfg.strategy_id,
        "profile": FIXED.profile,
        "seed_used": FIXED.seed,
        "window": {"from": window_from, "to": window_to},
        "dataset_path": result.dataset_path,
        "dataset_hash": result.dataset_hash,
        "metrics": dict(result.metrics),
        "trades": [trade.as_dict() for trade in result.trades],
    }
    _write_json(raw_path, payload)
    report = build_poc_report(raw_path)
    _write_json(report_json_path, report)
    report_md_path.write_text(render_poc_report_md(report), encoding="utf-8")
    return raw_path, report_json_path, report_md_path


def _overall_strict_pass(report: dict[str, Any]) -> bool:
    gate = report.get("acceptance_gate", {})
    checks = gate.get("checks", {})
    return bool(
        checks.get("avg_r_positive")
        and checks.get("pf_min_1_10")
        and checks.get("max_dd_le_0_30")
        and checks.get("trade_count_ge_300")
    )


def _validation_positive(report: dict[str, Any]) -> bool:
    summary = report.get("summary", {})
    return bool(
        float(summary.get("avg_r", 0.0)) > 0.0
        and float(summary.get("pf", 0.0)) >= 1.10
        and int(summary.get("count", 0)) >= 10
    )


def classify_strategy_status(
    *,
    lifecycle: str,
    report_2025: dict[str, Any],
    report_all: dict[str, Any],
) -> str:
    strict_all = _overall_strict_pass(report_all)
    val_positive = _validation_positive(report_2025)
    if strict_all and val_positive:
        if lifecycle == "research_only":
            return "validated_win_research_only"
        if lifecycle == "production_candidate":
            return "validated_win_production_candidate"
        return "validated_win"
    if val_positive:
        if lifecycle == "research_only":
            return "validated_mixed_research_only"
        return "validated_mixed"
    if lifecycle == "research_only":
        return "validated_fail_research_only"
    return "validated_fail"


def _strategy_row(
    *,
    cfg: StrategyReviewConfig,
    report_2025: dict[str, Any],
    report_all: dict[str, Any],
    raw_paths: dict[str, Path],
    report_paths: dict[str, Path],
) -> dict[str, Any]:
    summary_2025 = report_2025.get("summary", {})
    summary_all = report_all.get("summary", {})
    status = classify_strategy_status(
        lifecycle=cfg.lifecycle,
        report_2025=report_2025,
        report_all=report_all,
    )
    notes = list(cfg.notes)
    weak_points = report_all.get("weak_points", [])
    if weak_points:
        first = weak_points[0]
        notes.append(
            f"top_weak_point={first.get('scope')}:{first.get('key', 'overall')} avg_r={first.get('avg_r')}"
        )
    return {
        "strategy_id": cfg.strategy_id,
        "status": status,
        "lifecycle": cfg.lifecycle,
        "comparable_2022_2025": True,
        "metrics_2025": report_2025.get("metrics", {}),
        "metrics_2022_2025": report_all.get("metrics", {}),
        "summary_2025": {
            "avg_r": summary_2025.get("avg_r"),
            "pf": summary_2025.get("pf"),
            "trades": summary_2025.get("count"),
        },
        "summary_2022_2025": {
            "avg_r": summary_all.get("avg_r"),
            "pf": summary_all.get("pf"),
            "trades": summary_all.get("count"),
        },
        "acceptance_2025": report_2025.get("acceptance_gate", {}),
        "acceptance_2022_2025": report_all.get("acceptance_gate", {}),
        "weak_points_2022_2025": weak_points,
        "next_actions_2022_2025": report_all.get("next_actions", []),
        "evidence": [
            str(raw_paths["2025"]),
            str(raw_paths["2022_2025"]),
            str(report_paths["2025"]),
            str(report_paths["2022_2025"]),
        ],
        "notes": notes,
    }


def _render_registry_md(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Strategy PoC Registry ({payload['generated_at_utc'][:10]})")
    lines.append("")
    lines.append(f"- generated_at_utc: `{payload['generated_at_utc']}`")
    lines.append("- scope: USDJPY / M5 / UTC")
    lines.append(
        "- strict win definition (2022-2025): `avg_r>0 and pf>=1.1 and max_dd<=0.30 and trades>=300`"
    )
    lines.append(f"- strict winners: `{', '.join(payload['strict_winners']) or 'none'}`")
    lines.append("")
    lines.append("| strategy_id | lifecycle | status | 2025 | 2022-2025 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for strategy_id in payload["strategy_inventory"]:
        row = payload["summary"][strategy_id]
        m2025 = row["summary_2025"]
        mall = row["summary_2022_2025"]
        lines.append(
            f"| `{strategy_id}` | `{row['lifecycle']}` | `{row['status']}` | "
            f"avg_r={m2025['avg_r']}, pf={m2025['pf']}, trades={m2025['trades']} | "
            f"avg_r={mall['avg_r']}, pf={mall['pf']}, trades={mall['trades']} |"
        )
    lines.append("")
    lines.append("## Next Actions")
    lines.append("")
    for action in payload["next_actions"]:
        lines.append(f"- {action}")
    lines.append("")
    return "\n".join(lines)


def build_registry(stamp: str, strategies: list[str] | None = None) -> tuple[Path, Path]:
    selected = [
        cfg for cfg in STRATEGY_CONFIGS if strategies is None or cfg.strategy_id in set(strategies)
    ]
    summary: dict[str, Any] = {}
    strict_winners: list[str] = []
    for cfg in selected:
        raw_paths: dict[str, Path] = {}
        report_paths: dict[str, Path] = {}
        reports: dict[str, dict[str, Any]] = {}
        for window_name, window_from, window_to in WINDOWS:
            raw_path, report_json_path, report_md_path = _run_poc(
                cfg=cfg,
                window_name=window_name,
                window_from=window_from,
                window_to=window_to,
                stamp=stamp,
            )
            raw_paths[window_name] = raw_path
            report_paths[window_name] = report_json_path
            reports[window_name] = json.loads(report_json_path.read_text(encoding="utf-8"))
        row = _strategy_row(
            cfg=cfg,
            report_2025=reports["2025"],
            report_all=reports["2022_2025"],
            raw_paths=raw_paths,
            report_paths=report_paths,
        )
        summary[cfg.strategy_id] = row
        if _overall_strict_pass(reports["2022_2025"]):
            strict_winners.append(cfg.strategy_id)

    next_actions: list[str] = []
    for strategy_id in (cfg.strategy_id for cfg in selected):
        row = summary[strategy_id]
        if row["status"] in {"validated_fail", "validated_fail_research_only"}:
            next_actions.append(f"Rework or de-prioritize {strategy_id}; overall fixed-assumption gate failed.")
        elif row["status"] == "validated_mixed":
            next_actions.append(f"Find weak buckets for {strategy_id} and apply minimal filters before promotion.")

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "scope": {
            "symbol": "USDJPY",
            "timeframe": "M5",
            "timezone_basis": "UTC",
            "fixed_assumptions": asdict(FIXED),
        },
        "strategy_inventory": [cfg.strategy_id for cfg in selected],
        "summary": summary,
        "strict_win_definition": {
            "window": "2022-01-01..2025-12-31",
            "conditions": [
                "avg_r > 0",
                "pf_all >= 1.1",
                "max_drawdown <= 0.30",
                "trades >= 300",
            ],
        },
        "strict_winners": strict_winners,
        "strict_winner_count": len(strict_winners),
        "next_actions": next_actions,
    }
    json_path = VALIDATION_LOG_DIR / f"strategy_poc_registry_{stamp}.json"
    md_path = ANALYSIS_DIR / f"strategy_poc_registry_{stamp}.md"
    _write_json(json_path, payload)
    md_path.write_text(_render_registry_md(payload), encoding="utf-8")
    return json_path, md_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stamp", default=_utc_stamp(), help="UTC suffix used in output file names.")
    parser.add_argument(
        "--strategies",
        nargs="*",
        help="Optional subset of strategy IDs to review.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    json_path, md_path = build_registry(args.stamp, args.strategies)
    print(json.dumps({"registry_json": str(json_path), "registry_md": str(md_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
