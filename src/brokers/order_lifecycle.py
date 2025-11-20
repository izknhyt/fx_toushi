"""Order lifecycle manager stub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True)
class OrderEvent:
    order_id: str
    status: Literal["submitted", "filled", "cancelled"]


class OrderLifecycleManager:
    def __init__(self) -> None:
        self._events: list[OrderEvent] = []

    def record(self, event: OrderEvent) -> None:
        self._events.append(event)

    def history(self) -> list[OrderEvent]:
        return list(self._events)


__all__ = ["OrderLifecycleManager", "OrderEvent"]
