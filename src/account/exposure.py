"""Exposure helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(slots=True)
class ExposureBreakdown:
    buckets: Mapping[str, float] = field(default_factory=dict)

    def net(self) -> float:
        return sum(self.buckets.values())


__all__ = ["ExposureBreakdown"]
