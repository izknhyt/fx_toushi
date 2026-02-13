"""Overnight optimizer for m1_asia_compression_expansion_breakout.

This script performs two-stage random search with fixed PoC assumptions:
1) Stage-1 broad random search on train window
2) Stage-2 biased random search around top train candidates
Then it evaluates top candidates on validation window (no-retune),
selects the best case, and exports all-period/yearly summaries.
"""

from __future__ import annotations

import argparse
import json
import random
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import yaml

from src.backtest.paper_poc import simulate_paper_poc


@dataclass(frozen=True, slots=True)
class Window:
    start: str
    end: str


DEFAULT_SEARCH_SPACE: dict[str, list[Any]] = {
    "compression_minutes": [180, 240, 300, 360],
    "breakout_session_utc_range": ["06-14", "07-14", "08-14"],
    "max_signals_per_session": [1, 2],
    "allowed_directions": ["long_short", "long_only", "short_only"],
    "min_compression_abs": [0.6, 0.8, 1.0, 1.2],
    "compression_atr_mult": [2.5, 3.0, 3.5, 4.0],
    "min_breakout_abs": [0.03, 0.04, 0.05, 0.06],
    "breakout_atr_mult": [0.10, 0.15, 0.20],
    "breakout_cost_mult": [1.0, 1.5, 2.0, 2.5],
    "expansion_min_abs": [0.01, 0.02, 0.03],
    "expansion_atr_mult": [0.03, 0.05, 0.08],
    "max_cost_to_range_ratio": [0.7, 1.0, 1.3],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rank_tuple(metrics: dict[str, Any], objective: str) -> tuple[float, float, float, float]:
    pf = float(metrics.get("pf_all", 0.0))
    max_dd = float(metrics.get("max_drawdown", 1.0))
    trades = float(metrics.get("trades", 0.0))
    if objective == "avg_r":
        primary = float(metrics.get("avg_r", -1e9))
    else:
        primary = float(metrics.get("end_equity", -1e18))
    return (primary, pf, -max_dd, trades)


def _make_case(rng: random.Random, search_space: dict[str, list[Any]], case_id: str) -> dict[str, Any]:
    case: dict[str, Any] = {"case_id": case_id}
    for key, values in search_space.items():
        case[key] = rng.choice(values)
    return case


def _make_biased_case(
    rng: random.Random,
    search_space: dict[str, list[Any]],
    seed_case: dict[str, Any],
    case_id: str,
    keep_seed_prob: float = 0.7,
) -> dict[str, Any]:
    case: dict[str, Any] = {"case_id": case_id}
    for key, values in search_space.items():
        if rng.random() < keep_seed_prob:
            case[key] = seed_case[key]
        else:
            case[key] = rng.choice(values)
    return case


def _case_key(case: dict[str, Any], keys: list[str]) -> tuple[Any, ...]:
    return tuple(case[key] for key in keys)


def _apply_case_params(base_payload: dict[str, Any], strategy_id: str, case: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(base_payload)
    params = payload["strategies"][strategy_id]["parameters"]
    entry = params["entry"]
    filters = entry["filters"]

    entry["compression_minutes"] = int(case["compression_minutes"])
    entry["breakout_session_utc_range"] = str(case["breakout_session_utc_range"])
    entry["max_signals_per_session"] = int(case["max_signals_per_session"])
    ad = str(case["allowed_directions"])
    if ad == "long_only":
        entry["allowed_directions"] = ["long"]
    elif ad == "short_only":
        entry["allowed_directions"] = ["short"]
    else:
        entry["allowed_directions"] = ["long", "short"]

    filters["min_compression_abs"] = float(case["min_compression_abs"])
    filters["compression_atr_mult"] = float(case["compression_atr_mult"])
    filters["min_breakout_abs"] = float(case["min_breakout_abs"])
    filters["breakout_atr_mult"] = float(case["breakout_atr_mult"])
    filters["breakout_cost_mult"] = float(case["breakout_cost_mult"])
    filters["expansion_min_abs"] = float(case["expansion_min_abs"])
    filters["expansion_atr_mult"] = float(case["expansion_atr_mult"])
    filters["max_cost_to_range_ratio"] = float(case["max_cost_to_range_ratio"])
    return payload


def _run_single_case(
    *,
    base_payload: dict[str, Any],
    case: dict[str, Any],
    strategy_id: str,
    profile: str,
    window: Window,
    spread: float,
    slippage: float,
    slippage_std: float,
    commission_pct: float,
    target_r: float,
    ttl_bars: int,
    seed: int,
    risk_policy_path: Path,
    data_manifest_path: Path,
    feature_config_path: Path,
) -> dict[str, Any]:
    payload = _apply_case_params(base_payload=base_payload, strategy_id=strategy_id, case=case)
    with TemporaryDirectory() as td:
        manifest_path = Path(td) / "strategy_manifest.runtime.yaml"
        manifest_path.write_text(
            "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        result = simulate_paper_poc(
            strategy=strategy_id,
            profile=profile,
            window_from=window.start,
            window_to=window.end,
            spread_pips=spread,
            slippage_pips=slippage,
            slippage_std=slippage_std,
            commission_pct=commission_pct,
            target_r_multiple=target_r,
            ttl_bars=ttl_bars,
            seed=seed,
            risk_policy_path=risk_policy_path,
            data_manifest_path=data_manifest_path,
            feature_config_path=feature_config_path,
            strategy_manifest_path=manifest_path,
        )
    return dict(result.metrics)


def _run_reference_strategy(
    *,
    strategy_id: str,
    profile: str,
    window: Window,
    spread: float,
    slippage: float,
    slippage_std: float,
    commission_pct: float,
    target_r: float,
    ttl_bars: int,
    seed: int,
    risk_policy_path: Path,
    data_manifest_path: Path,
    feature_config_path: Path,
    strategy_manifest_path: Path,
) -> dict[str, Any]:
    result = simulate_paper_poc(
        strategy=strategy_id,
        profile=profile,
        window_from=window.start,
        window_to=window.end,
        spread_pips=spread,
        slippage_pips=slippage,
        slippage_std=slippage_std,
        commission_pct=commission_pct,
        target_r_multiple=target_r,
        ttl_bars=ttl_bars,
        seed=seed,
        risk_policy_path=risk_policy_path,
        data_manifest_path=data_manifest_path,
        feature_config_path=feature_config_path,
        strategy_manifest_path=strategy_manifest_path,
    )
    return dict(result.metrics)


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize Asia compression strategy with fixed PoC assumptions.")
    parser.add_argument("--strategy-id", default="m1_asia_compression_expansion_breakout")
    parser.add_argument(
        "--strategy-manifest",
        type=Path,
        default=Path("config/strategy_manifest.asia_compression_expansion_experiment.yaml"),
    )
    parser.add_argument("--profile", default="m1_baseline")
    parser.add_argument("--risk-policy", type=Path, default=Path("config/risk_policy.yaml"))
    parser.add_argument("--data-manifest", type=Path, default=Path("reports/data_manifest.json"))
    parser.add_argument("--feature-config", type=Path, default=Path("config/feature_pipeline.yaml"))

    parser.add_argument("--train-from", default="2022-01-01")
    parser.add_argument("--train-to", default="2024-12-31")
    parser.add_argument("--val-from", default="2025-01-01")
    parser.add_argument("--val-to", default="2025-12-31")
    parser.add_argument("--all-from", default="2022-01-01")
    parser.add_argument("--all-to", default="2025-12-31")

    parser.add_argument("--stage1-cases", type=int, default=300)
    parser.add_argument("--stage2-cases", type=int, default=200)
    parser.add_argument("--refine-top-k", type=int, default=20)
    parser.add_argument("--val-top-k", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--objective", choices=["end_equity", "avg_r"], default="avg_r")

    parser.add_argument("--train-min-trades", type=int, default=300)
    parser.add_argument("--val-min-trades", type=int, default=10)
    parser.add_argument("--gate-pf-min", type=float, default=1.1)
    parser.add_argument("--gate-maxdd-max", type=float, default=0.30)
    parser.add_argument("--gate-avg-r-min", type=float, default=0.0)

    parser.add_argument("--spread", type=float, default=0.005)
    parser.add_argument("--slippage", type=float, default=0.0015)
    parser.add_argument("--slippage-std", type=float, default=0.001)
    parser.add_argument("--commission-pct", type=float, default=0.0)
    parser.add_argument("--target-r", type=float, default=1.8)
    parser.add_argument("--ttl-bars", type=int, default=10)

    parser.add_argument("--compare-strategy", default=None)
    parser.add_argument("--compare-manifest", type=Path, default=Path("config/strategy_manifest.orb_vwap_experiment.yaml"))
    parser.add_argument("--output-prefix", default="asia_compression_opt")
    parser.add_argument("--validation-dir", type=Path, default=Path("reports/validation_log"))
    parser.add_argument("--analysis-dir", type=Path, default=Path("reports/analysis"))
    args = parser.parse_args()

    rng = random.Random(args.seed)
    search_keys = list(DEFAULT_SEARCH_SPACE.keys())
    strategy_manifest_payload = yaml.safe_load(args.strategy_manifest.read_text(encoding="utf-8"))

    train_window = Window(args.train_from, args.train_to)
    val_window = Window(args.val_from, args.val_to)
    all_window = Window(args.all_from, args.all_to)

    cases: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    def add_case(candidate: dict[str, Any]) -> bool:
        key = _case_key(candidate, search_keys)
        if key in seen:
            return False
        seen.add(key)
        cases.append(candidate)
        return True

    case_index = 1
    while len(cases) < args.stage1_cases:
        add_case(_make_case(rng, DEFAULT_SEARCH_SPACE, f"c{case_index:04d}"))
        case_index += 1

    train_rows: list[dict[str, Any]] = []
    for idx, case in enumerate(cases, 1):
        print(f"[train stage1] {idx}/{len(cases)} {case['case_id']}", flush=True)
        metrics = _run_single_case(
            base_payload=strategy_manifest_payload,
            case=case,
            strategy_id=args.strategy_id,
            profile=args.profile,
            window=train_window,
            spread=args.spread,
            slippage=args.slippage,
            slippage_std=args.slippage_std,
            commission_pct=args.commission_pct,
            target_r=args.target_r,
            ttl_bars=args.ttl_bars,
            seed=args.seed,
            risk_policy_path=args.risk_policy,
            data_manifest_path=args.data_manifest,
            feature_config_path=args.feature_config,
        )
        train_rows.append({"case": case, "train": {"metrics": metrics}})

    train_rows.sort(key=lambda row: _rank_tuple(row["train"]["metrics"], args.objective), reverse=True)
    seed_pool = train_rows[: max(1, args.refine_top_k)]

    target_total = args.stage1_cases + args.stage2_cases
    while len(cases) < target_total:
        source = rng.choice(seed_pool)["case"]
        candidate = _make_biased_case(
            rng=rng,
            search_space=DEFAULT_SEARCH_SPACE,
            seed_case=source,
            case_id=f"c{case_index:04d}",
        )
        case_index += 1
        if not add_case(candidate):
            continue
        print(f"[train stage2] {len(cases)}/{target_total} {candidate['case_id']}", flush=True)
        metrics = _run_single_case(
            base_payload=strategy_manifest_payload,
            case=candidate,
            strategy_id=args.strategy_id,
            profile=args.profile,
            window=train_window,
            spread=args.spread,
            slippage=args.slippage,
            slippage_std=args.slippage_std,
            commission_pct=args.commission_pct,
            target_r=args.target_r,
            ttl_bars=args.ttl_bars,
            seed=args.seed,
            risk_policy_path=args.risk_policy,
            data_manifest_path=args.data_manifest,
            feature_config_path=args.feature_config,
        )
        train_rows.append({"case": candidate, "train": {"metrics": metrics}})

    train_rows.sort(key=lambda row: _rank_tuple(row["train"]["metrics"], args.objective), reverse=True)
    train_filtered = [
        row for row in train_rows if int(row["train"]["metrics"].get("trades", 0)) >= args.train_min_trades
    ]
    val_targets = (train_filtered if train_filtered else train_rows)[: max(1, args.val_top_k)]

    for idx, row in enumerate(val_targets, 1):
        print(f"[val] {idx}/{len(val_targets)} {row['case']['case_id']}", flush=True)
        metrics = _run_single_case(
            base_payload=strategy_manifest_payload,
            case=row["case"],
            strategy_id=args.strategy_id,
            profile=args.profile,
            window=val_window,
            spread=args.spread,
            slippage=args.slippage,
            slippage_std=args.slippage_std,
            commission_pct=args.commission_pct,
            target_r=args.target_r,
            ttl_bars=args.ttl_bars,
            seed=args.seed,
            risk_policy_path=args.risk_policy,
            data_manifest_path=args.data_manifest,
            feature_config_path=args.feature_config,
        )
        row["val"] = {"metrics": metrics}

    val_filtered = [row for row in val_targets if int(row["val"]["metrics"].get("trades", 0)) >= args.val_min_trades]
    selection_pool = val_filtered if val_filtered else val_targets
    selection_pool.sort(key=lambda row: _rank_tuple(row["val"]["metrics"], args.objective), reverse=True)
    best = selection_pool[0]

    best_case = best["case"]
    print(f"[select] {best_case['case_id']}", flush=True)
    all_metrics = _run_single_case(
        base_payload=strategy_manifest_payload,
        case=best_case,
        strategy_id=args.strategy_id,
        profile=args.profile,
        window=all_window,
        spread=args.spread,
        slippage=args.slippage,
        slippage_std=args.slippage_std,
        commission_pct=args.commission_pct,
        target_r=args.target_r,
        ttl_bars=args.ttl_bars,
        seed=args.seed,
        risk_policy_path=args.risk_policy,
        data_manifest_path=args.data_manifest,
        feature_config_path=args.feature_config,
    )

    years = range(int(args.all_from[:4]), int(args.all_to[:4]) + 1)
    yearly_metrics: dict[str, Any] = {}
    for year in years:
        year_window = Window(f"{year}-01-01", f"{year}-12-31")
        yearly_metrics[str(year)] = _run_single_case(
            base_payload=strategy_manifest_payload,
            case=best_case,
            strategy_id=args.strategy_id,
            profile=args.profile,
            window=year_window,
            spread=args.spread,
            slippage=args.slippage,
            slippage_std=args.slippage_std,
            commission_pct=args.commission_pct,
            target_r=args.target_r,
            ttl_bars=args.ttl_bars,
            seed=args.seed,
            risk_policy_path=args.risk_policy,
            data_manifest_path=args.data_manifest,
            feature_config_path=args.feature_config,
        )

    acceptance = {
        "avg_r_gte_min": float(best["val"]["metrics"].get("avg_r", -1e9)) >= args.gate_avg_r_min,
        "pf_gte_min": float(best["val"]["metrics"].get("pf_all", 0.0)) >= args.gate_pf_min,
        "maxdd_lte_max": float(best["val"]["metrics"].get("max_drawdown", 1.0)) <= args.gate_maxdd_max,
        "train_trades_gte_min": int(best["train"]["metrics"].get("trades", 0)) >= args.train_min_trades,
        "val_trades_gte_min": int(best["val"]["metrics"].get("trades", 0)) >= args.val_min_trades,
    }
    acceptance["passed"] = all(acceptance.values())

    comparison: dict[str, Any] | None = None
    if args.compare_strategy:
        reference_val = _run_reference_strategy(
            strategy_id=args.compare_strategy,
            profile=args.profile,
            window=val_window,
            spread=args.spread,
            slippage=args.slippage,
            slippage_std=args.slippage_std,
            commission_pct=args.commission_pct,
            target_r=args.target_r,
            ttl_bars=args.ttl_bars,
            seed=args.seed,
            risk_policy_path=args.risk_policy,
            data_manifest_path=args.data_manifest,
            feature_config_path=args.feature_config,
            strategy_manifest_path=args.compare_manifest,
        )
        reference_all = _run_reference_strategy(
            strategy_id=args.compare_strategy,
            profile=args.profile,
            window=all_window,
            spread=args.spread,
            slippage=args.slippage,
            slippage_std=args.slippage_std,
            commission_pct=args.commission_pct,
            target_r=args.target_r,
            ttl_bars=args.ttl_bars,
            seed=args.seed,
            risk_policy_path=args.risk_policy,
            data_manifest_path=args.data_manifest,
            feature_config_path=args.feature_config,
            strategy_manifest_path=args.compare_manifest,
        )
        comparison = {
            "strategy": args.compare_strategy,
            "val": {
                "reference": reference_val,
                "delta_selected_minus_reference": {
                    "avg_r": round(float(best["val"]["metrics"].get("avg_r", 0.0)) - float(reference_val.get("avg_r", 0.0)), 4),
                    "pf_all": round(float(best["val"]["metrics"].get("pf_all", 0.0)) - float(reference_val.get("pf_all", 0.0)), 4),
                    "max_drawdown": round(
                        float(best["val"]["metrics"].get("max_drawdown", 0.0)) - float(reference_val.get("max_drawdown", 0.0)),
                        4,
                    ),
                    "trades": int(best["val"]["metrics"].get("trades", 0)) - int(reference_val.get("trades", 0)),
                },
            },
            "all": {
                "reference": reference_all,
                "delta_selected_minus_reference": {
                    "avg_r": round(float(all_metrics.get("avg_r", 0.0)) - float(reference_all.get("avg_r", 0.0)), 4),
                    "pf_all": round(float(all_metrics.get("pf_all", 0.0)) - float(reference_all.get("pf_all", 0.0)), 4),
                    "max_drawdown": round(float(all_metrics.get("max_drawdown", 0.0)) - float(reference_all.get("max_drawdown", 0.0)), 4),
                    "trades": int(all_metrics.get("trades", 0)) - int(reference_all.get("trades", 0)),
                },
            },
        }

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.validation_dir.mkdir(parents=True, exist_ok=True)
    args.analysis_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "generated_at": _utc_now(),
        "strategy_id": args.strategy_id,
        "fixed_assumptions": {
            "symbol": "USDJPY",
            "timeframe": "M5",
            "timezone": "UTC",
            "spread": args.spread,
            "slippage": args.slippage,
            "slippage_std": args.slippage_std,
            "commission_pct": args.commission_pct,
            "target_r": args.target_r,
            "ttl_bars": args.ttl_bars,
            "seed": args.seed,
            "profile": args.profile,
            "risk_policy": str(args.risk_policy),
        },
        "search": {
            "objective": args.objective,
            "tie_breaker": "pf_all desc -> max_drawdown asc -> trades desc",
            "stage1_cases": args.stage1_cases,
            "stage2_cases": args.stage2_cases,
            "executed_cases": len(cases),
            "refine_top_k": args.refine_top_k,
            "val_top_k": args.val_top_k,
            "train_window": {"from": train_window.start, "to": train_window.end},
            "val_window": {"from": val_window.start, "to": val_window.end},
            "all_window": {"from": all_window.start, "to": all_window.end},
            "constraints": {
                "train_min_trades": args.train_min_trades,
                "val_min_trades": args.val_min_trades,
            },
            "gate": {
                "avg_r_min": args.gate_avg_r_min,
                "pf_min": args.gate_pf_min,
                "maxdd_max": args.gate_maxdd_max,
            },
        },
        "cases": [
            {
                "case_id": row["case"]["case_id"],
                "params": {k: v for k, v in row["case"].items() if k != "case_id"},
                "train": row["train"]["metrics"],
                "val": row.get("val", {}).get("metrics"),
            }
            for row in train_rows
        ],
        "selected_case": {
            "case_id": best_case["case_id"],
            "params": {k: v for k, v in best_case.items() if k != "case_id"},
            "train_metrics": best["train"]["metrics"],
            "val_metrics": best["val"]["metrics"],
            "all_metrics": all_metrics,
            "train": best["train"]["metrics"],
            "val": best["val"]["metrics"],
            "all": all_metrics,
            "yearly_metrics": yearly_metrics,
        },
        "acceptance_gate": acceptance,
        "comparison": comparison,
    }

    prefix = f"{args.output_prefix}_{ts}"
    cases_path = args.validation_dir / f"{prefix}_cases.json"
    summary_path = args.validation_dir / f"{prefix}_search_summary.json"
    best_val_path = args.validation_dir / f"{prefix}_best_val.json"
    best_all_path = args.validation_dir / f"{prefix}_best_all.json"
    yearly_path = args.analysis_dir / f"{prefix}_yearly.json"
    markdown_path = args.analysis_dir / f"{prefix}_summary.md"

    cases_path.write_text(
        json.dumps({"generated_at": _utc_now(), "cases": cases}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    best_val_path.write_text(
        json.dumps(
            {
                "generated_at": _utc_now(),
                "case_id": best_case["case_id"],
                "params": {k: v for k, v in best_case.items() if k != "case_id"},
                "metrics": best["val"]["metrics"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    best_all_path.write_text(
        json.dumps(
            {
                "generated_at": _utc_now(),
                "case_id": best_case["case_id"],
                "params": {k: v for k, v in best_case.items() if k != "case_id"},
                "metrics": all_metrics,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    yearly_path.write_text(
        json.dumps(
            {
                "generated_at": _utc_now(),
                "case_id": best_case["case_id"],
                "yearly_metrics": yearly_metrics,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# Asia Compression Overnight Optimization Summary",
        "",
        f"- Generated at: `{_utc_now()}`",
        f"- Selected case: `{best_case['case_id']}`",
        f"- Objective: `{args.objective}`",
        f"- Acceptance passed: `{acceptance['passed']}`",
        "",
        "## Selected Params",
    ]
    for key, value in sorted({k: v for k, v in best_case.items() if k != "case_id"}.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Metrics",
            (
                f"- Train avg_r/pf/maxdd/trades/end_equity: "
                f"{best['train']['metrics'].get('avg_r')} / {best['train']['metrics'].get('pf_all')} / "
                f"{best['train']['metrics'].get('max_drawdown')} / {best['train']['metrics'].get('trades')} / "
                f"{best['train']['metrics'].get('end_equity')}"
            ),
            (
                f"- Val avg_r/pf/maxdd/trades/end_equity: "
                f"{best['val']['metrics'].get('avg_r')} / {best['val']['metrics'].get('pf_all')} / "
                f"{best['val']['metrics'].get('max_drawdown')} / {best['val']['metrics'].get('trades')} / "
                f"{best['val']['metrics'].get('end_equity')}"
            ),
            (
                f"- All avg_r/pf/maxdd/trades/end_equity: "
                f"{all_metrics.get('avg_r')} / {all_metrics.get('pf_all')} / {all_metrics.get('max_drawdown')} / "
                f"{all_metrics.get('trades')} / {all_metrics.get('end_equity')}"
            ),
        ]
    )
    if comparison is not None:
        lines.extend(
            [
                "",
                f"## Comparison vs `{comparison['strategy']}`",
                (
                    f"- Val delta: "
                    f"{comparison['val']['delta_selected_minus_reference']}"
                ),
                (
                    f"- All delta: "
                    f"{comparison['all']['delta_selected_minus_reference']}"
                ),
            ]
        )
    lines.extend(["", "## Yearly"])
    for year, metrics in yearly_metrics.items():
        lines.append(
            f"- {year}: avg_r={metrics.get('avg_r')}, pf={metrics.get('pf_all')}, "
            f"maxdd={metrics.get('max_drawdown')}, trades={metrics.get('trades')}, "
            f"end_equity={metrics.get('end_equity')}"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "selected_case": best_case["case_id"],
                "acceptance_passed": acceptance["passed"],
                "summary_path": str(summary_path),
                "markdown_path": str(markdown_path),
                "best_val_path": str(best_val_path),
                "best_all_path": str(best_all_path),
                "yearly_path": str(yearly_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
