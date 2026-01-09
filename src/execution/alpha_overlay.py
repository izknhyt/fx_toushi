"""Hands-off sizing helpers (lot ladder + auto-execute guardrails)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from src.analytics.pnl_feedback import FeedbackVector, apply_dynamic_adjustment


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
    return not (rule.watchlist_max is not None and watchlist > rule.watchlist_max)


def apply_lot_ladder(
    *,
    base_size: float,
    board_mode: str,
    auto_execute: bool,
    reduce_only: bool = False,
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

    if (
        not auto_execute
        or reduce_only
        or board_mode.lower() in {"guarded", "halted", "halt"}
        or watchlist > 0
    ):
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


def apply_hands_off_sizing(
    *,
    base_size: float,
    board_mode: str,
    auto_execute: bool,
    reduce_only: bool,
    lot_ladder: Iterable[LotLadderRule],
    pf_all: float,
    sharpe: float,
    maxdd_pct: float,
    watchlist: int,
    feedback: FeedbackVector | None = None,
    max_dynamic_adjust_pct: float = 0.15,
    dynamic_enabled: bool = True,
    spread_penalty: float | None = None,
    latency_p95_ms: float | None = None,
) -> tuple[float, float, bool]:
    """Compose lot ladder + dynamic adjustment for hands-off sizing.

    Returns (adjusted_size, ladder_factor, dynamic_applied).
    """

    size_after_ladder, ladder_factor = apply_lot_ladder(
        base_size=base_size,
        board_mode=board_mode,
        auto_execute=auto_execute,
        reduce_only=reduce_only,
        lot_ladder=lot_ladder,
        pf_all=pf_all,
        sharpe=sharpe,
        maxdd_pct=maxdd_pct,
        watchlist=watchlist,
        max_dynamic_adjust_pct=max_dynamic_adjust_pct,
    )
    if not feedback:
        return size_after_ladder, ladder_factor, False
    conv, size_after_dynamic, applied = apply_dynamic_adjustment(
        conviction=1.0,  # conviction is not tracked here; use neutral 1.0
        size=size_after_ladder,
        feedback=feedback,
        max_dynamic_adjust_pct=max_dynamic_adjust_pct,
        dynamic_enabled=dynamic_enabled,
        spread_penalty=spread_penalty,
        latency_p95_ms=latency_p95_ms,
    )
    _ = conv  # conviction unused in current call sites
    return size_after_dynamic, ladder_factor, applied
