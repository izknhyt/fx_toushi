"""Order routing interfaces shared across execution-facing modules."""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class OrderRouterProtocol(Protocol):
    """Protocol describing the interaction with broker/venue routers."""

    def submit(self, order_payload: Mapping[str, Any]) -> str:
        """Submit an order and return an identifier supplied by the venue."""

    def cancel(self, order_id: str) -> None:
        """Cancel an existing order at the venue or broker."""


__all__ = ["OrderRouterProtocol"]
