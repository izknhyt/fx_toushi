"""PnL feedback loop helpers for dynamic sizing/conviction adjustments."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeedbackVector:
    realized_rr: float
    target_rr: float
    max_adverse: float | None = None
    max_favorable: float | None = None
    slippage_bp: float | None = None


def apply_dynamic_adjustment(
    *,
    conviction: float,
    size: float,
    feedback: FeedbackVector,
    max_dynamic_adjust_pct: float = 0.15,
    dynamic_enabled: bool = True,
    spread_penalty: float | None = None,
    latency_p95_ms: float | None = None,
) -> tuple[float, float, bool]:
    """Adjust conviction/size within ±max_dynamic_adjust_pct based on RR gap.

    Returns (new_conviction, new_size, applied_flag).
    """

    if not dynamic_enabled:
        return conviction, size, False

    if spread_penalty is not None and spread_penalty > 0.05:
        return conviction, size, False
    if latency_p95_ms is not None and latency_p95_ms > 350:
        return conviction, size, False

    rr_gap = feedback.realized_rr - feedback.target_rr
    if rr_gap >= 0.5:
        delta = max_dynamic_adjust_pct
    elif rr_gap <= -0.5:
        delta = -max_dynamic_adjust_pct
    else:
        return conviction, size, False

    new_conviction = min(max(conviction * (1 + delta), 0.0), 1.0)
    new_size = size * (1 + delta)
    return new_conviction, new_size, True
