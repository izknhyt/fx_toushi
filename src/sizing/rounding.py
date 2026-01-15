"""Broker lot rounding utility."""

from __future__ import annotations

import math


def round_lot(size: float, *, lot_step: float = 0.01) -> float:
    if lot_step <= 0:
        raise ValueError("lot_step must be positive")
    stepped = math.floor(size / lot_step) * lot_step
    if stepped <= 0:
        stepped = lot_step
    return float(stepped)


__all__ = ["round_lot"]
