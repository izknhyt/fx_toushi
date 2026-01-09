"""Reduce-only advisor contracts used by the execution pipeline."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable


@runtime_checkable
class ReduceOnlyAdvisorProtocol(Protocol):
    """Protocol for components suggesting reduce-only actions."""

    def generate(self, *, account_state: object, spread_state: object) -> Iterable[object]:
        """Return advisory objects describing reduce-only requirements."""


__all__ = ["ReduceOnlyAdvisorProtocol"]
