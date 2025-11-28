"""Hands-off sizing helpers (lot ladder + auto-execute guardrails)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class LotLadderRule:
    pf_min: float | None = None
    sharpe_min: float | None = None
    maxdd_max: float | None = None
    watchlist_max: int | None = None
    size_factor: float = 1.0


def _meets(rule: LotLadderRule, *, pf: float, sharpe: float, maxdd: float, watchlist: int) -> bool:
    if rule.pf_min is not None and pf < rule.pf_min:
        return False
    if rule.sharpe_min is not None and sharpe < rule.sharpe_min:
        return False
    if rule.maxdd_max is not None and maxdd > rule.maxdd_max:
        return False
    if rule.watchlist_max is not None and watchlist > rule.watchlist_max:
        return False
    return True


def apply_lot_ladder(
    *,
    base_size: float,
    board_mode: str,
    auto_execute: bool,
    lot_ladder: Iterable[LotLadderRule],
    pf_all: float,
    sharpe: float,
    maxdd_pct: float,
    watchlist: int,
    max_dynamic_adjust_pct: float = 0.15,
) -> tuple[float, float]:
    """Return (adjusted_size, applied_factor) respecting board/auto_execute guards.

    - Guarded/Halt or auto_execute=False -> factor=1.0
    - Otherwise choose the first matching rule (in given order), clip by max_dynamic_adjust_pct.
    """

    if not auto_execute or board_mode.lower() in {"guarded", "halted", "halt"}:
        return base_size, 1.0

    for rule in lot_ladder:
        if not _meets(rule, pf=pf_all, sharpe=sharpe, maxdd=maxdd_pct, watchlist=watchlist):
            continue
        desired = rule.size_factor
        upper = 1.0 + max_dynamic_adjust_pct
        lower = max(0.0, 1.0 - max_dynamic_adjust_pct)
        clipped = min(max(desired, lower), upper)
        return base_size * clipped, clipped

    return base_size, 1.0
