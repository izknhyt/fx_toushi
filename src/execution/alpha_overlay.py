"""Execution Alpha overlay for sizing and protection hints (detailed design §88)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.analytics.pnl_feedback import FeedbackVector
from src.strategies.alpha_pulse import AlphaProfile, AlphaPulse


@dataclass(slots=True)
class AlphaOverlayResult:
    size_hint: float
    max_lot: float
    reduce_only: bool
    protect_levels: Mapping[str, Any]
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "size_hint": self.size_hint,
            "max_lot": self.max_lot,
            "reduce_only": self.reduce_only,
            "protect_levels": dict(self.protect_levels),
            "notes": list(self.notes),
        }


class ExecutionAlphaOverlay:
    def __init__(self, *, lot_ladder_factor: float = 1.0) -> None:
        self._lot_ladder_factor = lot_ladder_factor

    def apply(
        self,
        *,
        pulse: AlphaPulse,
        profile: AlphaProfile,
        board_mode: str = "normal",
        kill_switch: bool = False,
        auto_execute: bool = False,
        target_rr: float | None = None,
    ) -> AlphaOverlayResult:
        size_hint = float(pulse.size_band[1])
        notes: list[str] = []

        if board_mode == "guarded":
            size_hint *= 0.6
            notes.append("board_mode_guarded")
        elif board_mode == "halted":
            size_hint = 0.0
            notes.append("board_mode_halted")

        if auto_execute and board_mode == "normal":
            size_hint *= max(0.0, self._lot_ladder_factor)

        size_hint = min(size_hint, profile.max_lot)
        if pulse.reduce_only_hint or kill_switch or board_mode != "normal":
            reduce_only = True
            notes.append("reduce_only")
        else:
            reduce_only = False

        protect_levels = _build_protect_levels(
            target_rr=target_rr,
            reduce_only=reduce_only,
        )
        return AlphaOverlayResult(
            size_hint=round(size_hint, 6),
            max_lot=profile.max_lot,
            reduce_only=reduce_only,
            protect_levels=protect_levels,
            notes=tuple(notes),
        )


@dataclass(slots=True)
class LotLadderRule:
    pf_min: float | None = None
    sharpe_min: float | None = None
    maxdd_max: float | None = None
    watchlist_max: int | None = None
    size_factor: float = 1.0


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
    feedback: FeedbackVector | None,
    max_dynamic_adjust_pct: float,
    dynamic_enabled: bool,
    spread_penalty: float | None = None,
    latency_p95_ms: float | None = None,
) -> tuple[float, float, bool]:
    if not auto_execute or reduce_only or board_mode != "normal":
        return base_size, 1.0, False

    ladder_factor = 1.0
    for rule in lot_ladder:
        if rule.pf_min is not None and pf_all < rule.pf_min:
            continue
        if rule.sharpe_min is not None and sharpe < rule.sharpe_min:
            continue
        if rule.maxdd_max is not None and maxdd_pct > rule.maxdd_max:
            continue
        if rule.watchlist_max is not None and watchlist > rule.watchlist_max:
            continue
        ladder_factor = max(ladder_factor, rule.size_factor)

    adjusted_size = base_size * ladder_factor
    dynamic_applied = False
    if dynamic_enabled and feedback is not None:
        if spread_penalty is not None and spread_penalty > 0.05:
            return adjusted_size, ladder_factor, False
        if latency_p95_ms is not None and latency_p95_ms > 350:
            return adjusted_size, ladder_factor, False
        rr_gap = feedback.realized_rr - feedback.target_rr
        if abs(rr_gap) >= 0.5:
            direction = 1.0 if rr_gap > 0 else -1.0
            cap = max(0.0, min(max_dynamic_adjust_pct, 1.0))
            adj = cap * direction
            adjusted_size *= max(0.0, 1.0 + adj)
            dynamic_applied = True

    return adjusted_size, ladder_factor, dynamic_applied


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
    max_dynamic_adjust_pct: float | None = None,
) -> tuple[float, float]:
    if not auto_execute or board_mode != "normal":
        return base_size, 1.0
    ladder_factor = 1.0
    for rule in lot_ladder:
        if rule.pf_min is not None and pf_all < rule.pf_min:
            continue
        if rule.sharpe_min is not None and sharpe < rule.sharpe_min:
            continue
        if rule.maxdd_max is not None and maxdd_pct > rule.maxdd_max:
            continue
        if rule.watchlist_max is not None and watchlist > rule.watchlist_max:
            continue
        ladder_factor = max(ladder_factor, rule.size_factor)
    return base_size * ladder_factor, ladder_factor


def _build_protect_levels(*, target_rr: float | None, reduce_only: bool) -> Mapping[str, Any]:
    levels: dict[str, Any] = {
        "reduce_only_hint": reduce_only,
    }
    if target_rr is not None:
        levels["target_rr"] = target_rr
    return levels


__all__ = [
    "ExecutionAlphaOverlay",
    "AlphaOverlayResult",
    "LotLadderRule",
    "apply_lot_ladder",
    "apply_hands_off_sizing",
]
