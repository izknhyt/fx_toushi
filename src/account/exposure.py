"""Exposure helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(slots=True)
class ExposureBreakdown:
    buckets: Mapping[str, float] = field(default_factory=dict)

    def net(self) -> float:
        return sum(self.buckets.values())


__all__ = ["ExposureBreakdown"]
