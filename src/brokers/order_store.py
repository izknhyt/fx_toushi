"""Order state store stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class StoredOrder:
    order_id: str
    payload: dict[str, object]


class OrderStateStore:
    def __init__(self) -> None:
        self._orders: dict[str, StoredOrder] = {}

    def upsert(self, order: StoredOrder) -> None:
        self._orders[order.order_id] = order

    def get(self, order_id: str) -> StoredOrder | None:
        return self._orders.get(order_id)


__all__ = ["OrderStateStore", "StoredOrder"]
