"""Portfolio reallocation suggestions for sunset workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.governance.sunset import SunsetPlan


@dataclass(slots=True)
class ReallocationSuggestion:
    strategy_id: str
    action: str
    rationale: str

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "action": self.action,
            "rationale": self.rationale,
        }


class PortfolioReallocator:
    def suggest(self, plan: SunsetPlan, *, max_candidates: int = 5) -> list[ReallocationSuggestion]:
        suggestions: list[ReallocationSuggestion] = []
        if not plan.open_positions:
            suggestions.append(
                ReallocationSuggestion(
                    strategy_id=plan.strategy_id,
                    action="hold_cash",
                    rationale="No open positions; preserve capital until next allocation.",
                )
            )
            return suggestions
        suggestions.append(
            ReallocationSuggestion(
                strategy_id=plan.strategy_id,
                action="rebalance_core",
                rationale="Reallocate released capital to core strategies after sunset.",
            )
        )
        return suggestions[:max_candidates]


__all__ = ["PortfolioReallocator", "ReallocationSuggestion"]
