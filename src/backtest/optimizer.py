"""Grid/Random search optimizer utilities."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from random import Random
from typing import Any

from src.scoring.hybrid import compute_hybrid_score


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    parameters: Mapping[str, float]
    score: float
    metrics: Mapping[str, float]
    constraints_ok: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "parameters": dict(self.parameters),
            "score": self.score,
            "metrics": dict(self.metrics),
            "constraints_ok": self.constraints_ok,
        }


@dataclass(frozen=True, slots=True)
class OptimizationReport:
    search_space: Mapping[str, Sequence[float]]
    results: Sequence[OptimizationResult]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "search_space": {key: list(values) for key, values in self.search_space.items()},
            "results": [result.to_dict() for result in self.results],
        }


class OptimizationError(RuntimeError):
    """Optimizer errors (invalid search space or evaluation failure)."""


MetricEvaluator = Callable[[Mapping[str, float]], Mapping[str, float]]
Objective = Callable[[Mapping[str, float], Mapping[str, float]], float]
Constraint = Callable[[Mapping[str, float], Mapping[str, float]], bool]


class GridSearchOptimizer:
    def optimise(
        self,
        grid: Mapping[str, Iterable[float]],
        *,
        evaluator: MetricEvaluator,
        objective: Objective | None = None,
        constraints: Sequence[Constraint] | None = None,
        max_drawdown_threshold: float | None = None,
        random_samples: int | None = None,
        seed: int | None = None,
        report_path: Path | None = None,
    ) -> OptimizationReport:
        search_space = _coerce_grid(grid)
        if not search_space:
            raise OptimizationError("Search space is empty")
        if random_samples:
            results = _random_search(
                search_space,
                evaluator=evaluator,
                objective=objective,
                constraints=constraints,
                max_drawdown_threshold=max_drawdown_threshold,
                random_samples=random_samples,
                seed=seed,
            )
        else:
            results = _grid_search(
                search_space,
                evaluator=evaluator,
                objective=objective,
                constraints=constraints,
                max_drawdown_threshold=max_drawdown_threshold,
            )
        results.sort(key=lambda item: item.score, reverse=True)
        report = OptimizationReport(
            search_space=search_space,
            results=results,
            generated_at=_utcnow_iso(),
        )
        if report_path:
            _write_report(report_path, report)
        return report

    def optimize(self, *args: Any, **kwargs: Any) -> OptimizationReport:
        return self.optimise(*args, **kwargs)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _coerce_grid(grid: Mapping[str, Iterable[float]]) -> dict[str, Sequence[float]]:
    search_space: dict[str, Sequence[float]] = {}
    for key, values in grid.items():
        if isinstance(values, tuple):
            if not values:
                raise OptimizationError(f"Empty search space for {key}")
            search_space[str(key)] = values
            continue
        if isinstance(values, list):
            if not values:
                raise OptimizationError(f"Empty search space for {key}")
            search_space[str(key)] = values
            continue
        expanded = list(values)
        if not expanded:
            raise OptimizationError(f"Empty search space for {key}")
        search_space[str(key)] = expanded
    return search_space


def _default_objective(params: Mapping[str, float], metrics: Mapping[str, float]) -> float:
    if "hybrid_score" in metrics:
        return float(metrics["hybrid_score"])
    if {"alpha", "decay", "stability"}.issubset(metrics):
        hybrid = compute_hybrid_score(
            float(metrics["alpha"]),
            float(metrics["decay"]),
            float(metrics["stability"]),
            enabled=True,
        )
        return hybrid.composite
    if {"pf", "sharpe", "stability"}.issubset(metrics):
        hybrid = compute_hybrid_score(
            float(metrics["pf"]),
            float(metrics["sharpe"]),
            float(metrics["stability"]),
            enabled=True,
        )
        return hybrid.composite
    return 0.0


def _constraints_ok(
    params: Mapping[str, float],
    metrics: Mapping[str, float],
    constraints: Sequence[Constraint] | None,
    max_drawdown_threshold: float | None,
) -> bool:
    if max_drawdown_threshold is not None:
        max_dd = metrics.get("max_drawdown")
        if max_dd is None:
            return False
        if float(max_dd) > max_drawdown_threshold:
            return False
    if constraints:
        for constraint in constraints:
            if not constraint(params, metrics):
                return False
    return True


def _evaluate_candidate(
    params: Mapping[str, float],
    *,
    evaluator: MetricEvaluator,
    objective: Objective | None,
    constraints: Sequence[Constraint] | None,
    max_drawdown_threshold: float | None,
) -> OptimizationResult:
    metrics = evaluator(params)
    if not isinstance(metrics, Mapping):
        raise OptimizationError("Evaluator must return a mapping of metrics")
    score_fn = objective or _default_objective
    score = float(score_fn(params, metrics))
    constraints_ok = _constraints_ok(params, metrics, constraints, max_drawdown_threshold)
    return OptimizationResult(
        parameters=params,
        score=score if constraints_ok else float("-inf"),
        metrics=metrics,
        constraints_ok=constraints_ok,
    )


def _grid_search(
    search_space: Mapping[str, Sequence[float]],
    *,
    evaluator: MetricEvaluator,
    objective: Objective | None,
    constraints: Sequence[Constraint] | None,
    max_drawdown_threshold: float | None,
) -> list[OptimizationResult]:
    keys = list(search_space.keys())
    combos = product(*search_space.values())
    results: list[OptimizationResult] = []
    for combo in combos:
        params = dict(zip(keys, combo, strict=False))
        results.append(
            _evaluate_candidate(
                params,
                evaluator=evaluator,
                objective=objective,
                constraints=constraints,
                max_drawdown_threshold=max_drawdown_threshold,
            )
        )
    return results


def _random_search(
    search_space: Mapping[str, Sequence[float]],
    *,
    evaluator: MetricEvaluator,
    objective: Objective | None,
    constraints: Sequence[Constraint] | None,
    max_drawdown_threshold: float | None,
    random_samples: int,
    seed: int | None,
) -> list[OptimizationResult]:
    rng = Random(seed)
    results: list[OptimizationResult] = []
    for _ in range(random_samples):
        params: dict[str, float] = {}
        for key, values in search_space.items():
            if isinstance(values, tuple) and len(values) == 2 and all(
                isinstance(item, (int, float)) for item in values
            ):
                params[key] = rng.uniform(float(values[0]), float(values[1]))
            else:
                params[key] = rng.choice(list(values))
        results.append(
            _evaluate_candidate(
                params,
                evaluator=evaluator,
                objective=objective,
                constraints=constraints,
                max_drawdown_threshold=max_drawdown_threshold,
            )
        )
    return results


def _write_report(path: Path, report: OptimizationReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.to_dict()
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


__all__ = [
    "GridSearchOptimizer",
    "OptimizationResult",
    "OptimizationReport",
    "OptimizationError",
]
