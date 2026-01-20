"""Run regression backtests for CI and local validation."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.backtest.regression import (
    RegressionBacktestSuite,
    RegressionDataMismatch,
    RegressionScenario,
)
from src.governance.secure_share import SecureShareService


def _load_suite(args: argparse.Namespace) -> RegressionBacktestSuite:
    return RegressionBacktestSuite(
        scenarios_path=Path(args.scenarios),
        config_path=Path(args.config),
        output_root=Path(args.output_root),
        metrics_path=Path(args.metrics_path),
    )


def _resolve_scenario_paths(
    scenarios: list[RegressionScenario], bundle_root: str | None
) -> list[RegressionScenario]:
    if not bundle_root:
        return scenarios
    resolved: list[RegressionScenario] = []
    root = Path(bundle_root)
    for scenario in scenarios:
        bundle = Path(scenario.market_data_bundle)
        if not bundle.is_absolute():
            bundle = root / bundle
        resolved.append(
            RegressionScenario(
                scenario_id=scenario.scenario_id,
                strategy_id=scenario.strategy_id,
                window=scenario.window,
                market_data_bundle=str(bundle),
                expected_metrics=scenario.expected_metrics,
            )
        )
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", help="Run a single scenario id.")
    parser.add_argument(
        "--scenarios",
        default="config/regression_scenarios.yaml",
        help="Scenario registry path.",
    )
    parser.add_argument(
        "--config",
        default="config/regression.yaml",
        help="Regression config path.",
    )
    parser.add_argument(
        "--output-root",
        default="reports/regression/backtest",
        help="Root output directory.",
    )
    parser.add_argument(
        "--metrics-path",
        default="metrics/regression_backtest.jsonl",
        help="Metrics JSONL path.",
    )
    parser.add_argument(
        "--artifacts-dir",
        default="artifacts/regression",
        help="Artifacts export directory on failure.",
    )
    parser.add_argument(
        "--bundle-root",
        default=None,
        help="Optional root directory for scenario bundles.",
    )
    parser.add_argument(
        "--refresh-bundle",
        action="store_true",
        help="Generate change request template for bundle refresh.",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Prepare evidence bundle with SecureShare.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip SecureShare publishing.",
    )
    args = parser.parse_args(argv)

    if args.refresh_bundle:
        _generate_change_request()
        print("Generated regression bundle change request template.")
        return 0

    suite = _load_suite(args)
    try:
        if args.scenario:
            summary = suite.run_scenario(args.scenario)
        else:
            scenarios = suite.list_scenarios()
            scenarios = _resolve_scenario_paths(scenarios, args.bundle_root)
            summary = suite.run_scenarios(scenarios)
    except ValueError as exc:
        print(f"Regression configuration error: {exc}", file=sys.stderr)
        return 2
    except RegressionDataMismatch as exc:
        print(f"Regression bundle error: {exc}", file=sys.stderr)
        return 121
    except KeyError as exc:
        print(f"Regression scenario error: {exc}", file=sys.stderr)
        return 2

    summary_path = Path(summary.output_dir) / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "run_id": summary.run_id,
                "status": summary.status,
                "started_at": summary.started_at,
                "completed_at": summary.completed_at,
                "drift_count": len(summary.drifts),
                "scenarios": [result.scenario_id for result in summary.scenarios],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_validation_log(summary)

    if args.upload:
        _prepare_secure_share(summary, dry_run=args.dry_run)

    if summary.status != "pass":
        artifacts_root = Path(args.artifacts_dir)
        artifacts_root.mkdir(parents=True, exist_ok=True)
        target = artifacts_root / summary.run_id
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(summary.output_dir, target)
        return 121
    return 0


def _write_validation_log(summary: object) -> Path:
    now = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_dir = Path("reports") / "validation_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"AC-13_regression_{now}.md"
    lines = [
        "# AC-13 Regression Backtest Validation",
        "",
        f"- run_id: {summary.run_id}",
        f"- status: {summary.status}",
        f"- drift_count: {len(summary.drifts)}",
        f"- output_dir: {summary.output_dir}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _generate_change_request() -> Path:
    template = Path("docs") / "change_requests" / "REGRESSION_BUNDLE_TEMPLATE.md"
    target_dir = Path("docs") / "change_requests"
    target_dir.mkdir(parents=True, exist_ok=True)
    date_stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    target = target_dir / f"CR-{date_stamp}-regression-bundle.md"
    if template.exists():
        target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        target.write_text("# Regression Bundle Change Request\n", encoding="utf-8")
    return target


def _prepare_secure_share(summary: object, *, dry_run: bool) -> None:
    service = SecureShareService()
    output_dir = Path(summary.output_dir)
    sources = [output_dir]
    package, manifest_path = service.prepare_package(
        profile_id="research_validation",
        period=summary.run_id,
        sources=sources,
        created_by="regression-backtest",
    )
    encrypted_path = service.encrypt_package(package=package, manifest_path=manifest_path)
    if dry_run:
        return
    service.publish(package=package, encrypted_path=encrypted_path, channel="local")


if __name__ == "__main__":
    raise SystemExit(main())
