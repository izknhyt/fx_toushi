"""Broker lot rounding utility."""

from __future__ import annotations


def round_lot(size: float, *, lot_step: float = 0.01) -> float:
    if lot_step <= 0:
        raise ValueError("lot_step must be positive")
    rounded = round(size / lot_step) * lot_step
    return float(max(lot_step, rounded))


__all__ = ["round_lot"]
