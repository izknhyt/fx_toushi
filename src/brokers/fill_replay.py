"""Fill replay service stub."""

from __future__ import annotations

from typing import Iterable


class FillReplayService:
    def replay(self, order_ids: Iterable[str]) -> None:
        list(order_ids)


__all__ = ["FillReplayService"]
