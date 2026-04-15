"""FX rate utilities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FxRate:
    pair: str
    rate: float


class FxRateService:
    def get_rate(self, pair: str) -> FxRate:
        return FxRate(pair=pair.upper(), rate=1.0)


__all__ = ["FxRate", "FxRateService"]
