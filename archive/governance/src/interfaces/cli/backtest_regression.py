"""CLI helpers for regression backtests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.backtest.regression import RegressionBacktestSuite, RegressionDataMismatch

__all__ = ["regression_list", "regression_run"]


def regression_list(*, scenarios_path: Path) -> Mapping[str, Any]:
    suite = RegressionBacktestSuite(scenarios_path=scenarios_path)
    scenarios = suite.list_scenarios()
    return {
        "status": "ok",
        "count": len(scenarios),
        "scenarios": [scenario.to_dict() for scenario in scenarios],
    }


def regression_run(
    *,
    scenario_id: str,
    scenarios_path: Path,
    output_root: Path,
    metrics_path: Path,
) -> Mapping[str, Any]:
    suite = RegressionBacktestSuite(
        scenarios_path=scenarios_path,
        output_root=output_root,
        metrics_path=metrics_path,
    )
    try:
        summary = suite.run_scenario(scenario_id)
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}
    except KeyError as exc:
        return {"status": "error", "error": str(exc)}
    except RegressionDataMismatch as exc:
        return {"status": "error", "error": str(exc)}
    return {
        "status": summary.status,
        "run_id": summary.run_id,
        "output_dir": summary.output_dir,
        "drift_count": len(summary.drifts),
    }
