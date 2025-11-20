"""Fill shadow recorder stub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class FillRecord:
    order_id: str
    price: float


class FillShadowRecorder:
    def record(self, fills: Iterable[FillRecord]) -> None:
        _ = list(fills)


__all__ = ["FillShadowRecorder", "FillRecord"]
