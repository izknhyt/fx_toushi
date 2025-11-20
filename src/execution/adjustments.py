"""Execution adjustments dataclass referenced in §1.3."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ExecutionAdjustments:
    """Represents human/market adjustments to an execution price."""

    slippage_bps: float = 0.0
    spread_bps: float = 0.0
    hitl_latency_sec: float = 0.0

    def apply(self, price: float) -> float:
        """Apply the adjustments to ``price`` and return the adjusted value."""

        basis = price * (1 + (self.slippage_bps + self.spread_bps) / 10000)
        return basis


__all__ = ["ExecutionAdjustments"]
