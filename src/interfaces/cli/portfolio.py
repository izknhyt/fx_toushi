"""Portfolio CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.governance.sunset import StrategySunsetService
from src.portfolio.reallocation import PortfolioReallocator


def suggest_reallocation(
    *,
    plan_id: str,
    max_candidates: int,
    sunset_dir: Path,
) -> Mapping[str, Any]:
    service = StrategySunsetService(sunset_dir=sunset_dir)
    plan = service.load_plan(plan_id)
    suggestions = PortfolioReallocator().suggest(plan, max_candidates=max_candidates)
    return {
        "status": "ok",
        "plan_id": plan_id,
        "suggestions": [entry.to_dict() for entry in suggestions],
    }


__all__ = ["suggest_reallocation"]
