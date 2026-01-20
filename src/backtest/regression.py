"""Regression backtest suite for deterministic drift checks."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.backtest.engine import BacktestEngine
from src.core.health import HealthMonitor
from src.utils.hashing import sha256_path

DEFAULT_SCENARIOS_PATH = Path("config") / "regression_scenarios.yaml"
DEFAULT_CONFIG_PATH = Path("config") / "regression.yaml"
DEFAULT_OUTPUT_ROOT = Path("reports") / "regression" / "backtest"
DEFAULT_METRICS_PATH = Path("metrics") / "regression_backtest.jsonl"
DEFAULT_HEALTH_REASON = "regression_backtest_drift"
DEFAULT_RUNBOOK_REF = "STRAT-M1-VALIDATION#regression_check"


class RegressionDataMismatch(RuntimeError):
    """Raised when a regression bundle fails integrity checks."""


@dataclass(slots=True)
class RegressionExpectation:
    metric: str
    target: float
    tolerance: float
    metric_state: str | None = None


@dataclass(slots=True)
class RegressionScenario:
    scenario_id: str
    strategy_id: str
    window: str
    market_data_bundle: str
    expected_metrics: list[RegressionExpectation]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "regression.scenario.v1",
            "id": self.scenario_id,
            "strategy_id": self.strategy_id,
            "window": self.window,
            "market_data_bundle": self.market_data_bundle,
            "expected_metrics": [
                {
                    "metric": exp.metric,
                    "target": exp.target,
                    "tolerance": exp.tolerance,
                    "metric_state": exp.metric_state,
                }
                for exp in self.expected_metrics
            ],
        }


@dataclass(slots=True)
class RegressionDrift:
    scenario_id: str
    metric: str
    expected: float
    actual: float | None
    tolerance: float
    notes: str


@dataclass(slots=True)
class RegressionResult:
    scenario_id: str
    status: str
    metrics: Mapping[str, Any]
    drifts: list[RegressionDrift]
    artifacts: list[str]


@dataclass(slots=True)
class RegressionRunSummary:
    run_id: str
    status: str
    started_at: str
    completed_at: str
    scenarios: list[RegressionResult]
    drifts: list[RegressionDrift]
    output_dir: str


class RegressionBacktestSuite:
    def __init__(
        self,
        *,
        scenarios_path: Path = DEFAULT_SCENARIOS_PATH,
        config_path: Path = DEFAULT_CONFIG_PATH,
        output_root: Path = DEFAULT_OUTPUT_ROOT,
        metrics_path: Path = DEFAULT_METRICS_PATH,
    ) -> None:
        self._scenarios_path = scenarios_path
        self._config_path = config_path
        self._output_root = output_root
        self._metrics_path = metrics_path

    def list_scenarios(self) -> list[RegressionScenario]:
        return _load_scenarios(self._scenarios_path)

    def run_all(self) -> RegressionRunSummary:
        scenarios = self.list_scenarios()
        return self._run(scenarios)

    def run_scenario(self, scenario_id: str) -> RegressionRunSummary:
        scenarios = [s for s in self.list_scenarios() if s.scenario_id == scenario_id]
        if not scenarios:
            raise KeyError(f"scenario not found: {scenario_id}")
        return self._run(scenarios)

    def run_scenarios(self, scenarios: list[RegressionScenario]) -> RegressionRunSummary:
        return self._run(scenarios)

    def _run(self, scenarios: list[RegressionScenario]) -> RegressionRunSummary:
        if not scenarios:
            raise ValueError("no regression scenarios configured")
        run_id = _run_id()
        started_at = _utcnow_iso()
        output_dir = self._output_root / run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        config = _load_config(self._config_path)
        max_concurrency = max(1, int(config.get("max_concurrency", 2)))
        max_runtime_min = max(1, int(config.get("max_runtime_per_scenario_min", 20)))
        results = asyncio.run(
            _run_scenarios(
                scenarios,
                output_dir=output_dir,
                max_concurrency=max_concurrency,
                max_runtime_min=max_runtime_min,
            )
        )
        drifts = [drift for result in results for drift in result.drifts]
        status = "pass" if all(result.status == "pass" for result in results) else "fail"
        completed_at = _utcnow_iso()
        summary = RegressionRunSummary(
            run_id=run_id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            scenarios=results,
            drifts=drifts,
            output_dir=str(output_dir),
        )
        _write_summary_markdown(summary, output_dir)
        _append_metrics(summary, self._metrics_path)
        if status != "pass":
            HealthMonitor().raise_condition(
                "warn",
                DEFAULT_HEALTH_REASON,
                detail=f"drifts={len(drifts)}",
                recommended_action=f"runbook:{DEFAULT_RUNBOOK_REF}",
            )
        return summary


async def _run_scenarios(
    scenarios: list[RegressionScenario],
    *,
    output_dir: Path,
    max_concurrency: int,
    max_runtime_min: int,
) -> list[RegressionResult]:
    if not scenarios:
        return []

    semaphore = asyncio.Semaphore(max_concurrency)

    async def runner(scenario: RegressionScenario) -> RegressionResult:
        async with semaphore:
            return await asyncio.wait_for(
                asyncio.to_thread(_execute_scenario, scenario, output_dir),
                timeout=max_runtime_min * 60,
            )

    tasks = [asyncio.create_task(runner(scenario)) for scenario in scenarios]
    return list(await asyncio.gather(*tasks))


def _execute_scenario(scenario: RegressionScenario, output_dir: Path) -> RegressionResult:
    bundle_path, bundle_manifest = _load_bundle(Path(scenario.market_data_bundle))
    manifest_path = _write_manifest_override(
        output_dir,
        scenario_id=scenario.scenario_id,
        strategy_id=scenario.strategy_id,
        dataset_path=bundle_manifest["bars_path"],
        dataset_sha256=bundle_manifest["bars_sha256"],
    )
    engine = BacktestEngine(manifest_path=manifest_path)
    result = engine.run(strategy=scenario.strategy_id, profile="backtest")
    metrics = dict(result.metrics)
    drifts = _evaluate_metrics(scenario, metrics)
    status = "pass" if not drifts else "fail"
    artifacts = [str(manifest_path)]
    return RegressionResult(
        scenario_id=scenario.scenario_id,
        status=status,
        metrics=metrics,
        drifts=drifts,
        artifacts=artifacts,
    )


def _load_bundle(bundle_dir: Path) -> tuple[Path, dict[str, object]]:
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.exists():
        raise RegressionDataMismatch(f"bundle manifest missing: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    bars_path = Path(payload.get("bars_path") or "")
    if not bars_path.is_absolute():
        bars_path = bundle_dir / bars_path
    if not bars_path.exists():
        raise RegressionDataMismatch(f"bundle bars missing: {bars_path}")
    expected_hash = payload.get("bars_sha256")
    actual_hash = sha256_path(bars_path)
    if expected_hash and expected_hash != actual_hash:
        raise RegressionDataMismatch(
            f"bundle hash mismatch: expected={expected_hash} actual={actual_hash}"
        )
    payload = dict(payload)
    payload["bars_path"] = str(bars_path)
    payload["bars_sha256"] = expected_hash or actual_hash
    return bundle_dir, payload


def _write_manifest_override(
    output_dir: Path,
    *,
    scenario_id: str,
    strategy_id: str,
    dataset_path: str,
    dataset_sha256: str,
) -> Path:
    manifest_path = output_dir / f"manifest_{scenario_id}.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "strategies:",
                f"  {strategy_id}:",
                f"    dataset_path: {dataset_path}",
                f"    dataset_sha256: {dataset_sha256}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _evaluate_metrics(
    scenario: RegressionScenario, metrics: Mapping[str, Any]
) -> list[RegressionDrift]:
    drifts: list[RegressionDrift] = []
    for expectation in scenario.expected_metrics:
        actual = metrics.get(expectation.metric)
        if actual is None:
            drifts.append(
                RegressionDrift(
                    scenario_id=scenario.scenario_id,
                    metric=expectation.metric,
                    expected=expectation.target,
                    actual=None,
                    tolerance=expectation.tolerance,
                    notes="missing_metric",
                )
            )
            continue
        delta = abs(float(actual) - expectation.target)
        if delta > expectation.tolerance:
            drifts.append(
                RegressionDrift(
                    scenario_id=scenario.scenario_id,
                    metric=expectation.metric,
                    expected=expectation.target,
                    actual=float(actual),
                    tolerance=expectation.tolerance,
                    notes=f"delta={delta:.4f}",
                )
            )
    return drifts


def _load_scenarios(path: Path) -> list[RegressionScenario]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_scenarios = payload.get("scenarios") or []
    scenarios: list[RegressionScenario] = []
    for entry in raw_scenarios:
        if not isinstance(entry, dict):
            continue
        scenario_id = entry.get("id")
        strategy_id = entry.get("strategy_id")
        bundle = entry.get("market_data_bundle")
        if not scenario_id or not strategy_id or not bundle:
            continue
        expected_metrics = entry.get("expected_metrics") or []
        expectations = [
            RegressionExpectation(
                metric=str(metric.get("metric")),
                target=float(metric.get("target")),
                tolerance=float(metric.get("tolerance", 0)),
                metric_state=metric.get("metric_state"),
            )
            for metric in expected_metrics
            if isinstance(metric, dict) and metric.get("metric") is not None
        ]
        scenarios.append(
            RegressionScenario(
                scenario_id=str(scenario_id),
                strategy_id=str(strategy_id),
                window=str(entry.get("window")),
                market_data_bundle=str(bundle),
                expected_metrics=expectations,
            )
        )
    return scenarios


def _load_config(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _write_summary_markdown(summary: RegressionRunSummary, output_dir: Path) -> Path:
    lines = [
        f"# Regression Backtest Summary ({summary.run_id})",
        "",
        f"- Status: {summary.status}",
        f"- Started: {summary.started_at}",
        f"- Completed: {summary.completed_at}",
        f"- Scenarios: {len(summary.scenarios)}",
        "",
    ]
    if summary.drifts:
        lines.append("## Drift Details")
        for drift in summary.drifts:
            lines.append(
                f"- {drift.scenario_id} {drift.metric} expected={drift.expected} "
                f"actual={drift.actual} tol={drift.tolerance} ({drift.notes})"
            )
        lines.append("")
    lines.append("## Scenario Results")
    for result in summary.scenarios:
        lines.append(f"- {result.scenario_id}: {result.status}")
    output_path = output_dir / "summary.md"
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _append_metrics(summary: RegressionRunSummary, metrics_path: Path) -> None:
    payload = {
        "event": "regression_backtest.summary",
        "run_id": summary.run_id,
        "status": summary.status,
        "drift_count": len(summary.drifts),
        "scenario_count": len(summary.scenarios),
        "started_at": summary.started_at,
        "completed_at": summary.completed_at,
        "output_dir": summary.output_dir,
    }
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _run_id() -> str:
    now = datetime.now(timezone.utc)
    return f"{now:%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:8]}"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "RegressionBacktestSuite",
    "RegressionScenario",
    "RegressionResult",
    "RegressionDrift",
    "RegressionRunSummary",
    "RegressionDataMismatch",
]
