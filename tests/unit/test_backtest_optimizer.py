from __future__ import annotations

from pathlib import Path

from src.backtest.optimizer import GridSearchOptimizer


def test_grid_search_optimizer_applies_constraints(tmp_path: Path) -> None:
    grid = {"alpha": [0.1, 0.2], "decay": [0.2], "stability": [0.3]}

    def evaluator(params: dict[str, float]) -> dict[str, float]:
        return {
            "alpha": params["alpha"],
            "decay": params["decay"],
            "stability": params["stability"],
            "max_drawdown": params["alpha"] + 0.15,
        }

    optimizer = GridSearchOptimizer()
    report = optimizer.optimise(
        grid,
        evaluator=evaluator,
        max_drawdown_threshold=0.3,
        report_path=tmp_path / "optimizer.json",
    )

    assert report.results
    assert (tmp_path / "optimizer.json").exists()
    assert report.results[0].constraints_ok is True
    assert any(result.constraints_ok is False for result in report.results)


def test_random_search_respects_bounds() -> None:
    grid = {"alpha": (0.0, 1.0), "decay": (0.0, 1.0), "stability": (0.0, 1.0)}

    def evaluator(params: dict[str, float]) -> dict[str, float]:
        return {
            "alpha": params["alpha"],
            "decay": params["decay"],
            "stability": params["stability"],
            "max_drawdown": 0.1,
        }

    optimizer = GridSearchOptimizer()
    report = optimizer.optimise(
        grid,
        evaluator=evaluator,
        random_samples=5,
        seed=42,
        max_drawdown_threshold=0.3,
    )

    assert len(report.results) == 5
    for result in report.results:
        assert 0.0 <= result.parameters["alpha"] <= 1.0
        assert 0.0 <= result.parameters["decay"] <= 1.0
        assert 0.0 <= result.parameters["stability"] <= 1.0


def test_random_search_uses_discrete_values_for_lists() -> None:
    grid = {"alpha": [0.1, 0.2], "decay": [0.3], "stability": [0.4]}

    def evaluator(params: dict[str, float]) -> dict[str, float]:
        return {
            "alpha": params["alpha"],
            "decay": params["decay"],
            "stability": params["stability"],
            "max_drawdown": 0.1,
        }

    optimizer = GridSearchOptimizer()
    report = optimizer.optimise(
        grid,
        evaluator=evaluator,
        random_samples=6,
        seed=7,
        max_drawdown_threshold=0.3,
    )

    assert all(result.parameters["alpha"] in {0.1, 0.2} for result in report.results)
