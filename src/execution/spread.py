"""Spread monitoring contracts and type aliases used across the codebase."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from typing_extensions import Literal

SpreadCooldownState = Literal["normal", "watch", "cooldown", "halt"]
"""Spread guard state shared between execution, risk, and strategy layers."""


@dataclass(slots=True, frozen=True)
class SpreadSnapshot:
    """Minimal snapshot of spread metrics for a single symbol."""

    symbol: str
    spread_pips: float
    timestamp: datetime
    cooldown_state: SpreadCooldownState


class SpreadDataDegraded(RuntimeError):
    """Raised when spread data quality is insufficient for guard decisions."""


@runtime_checkable
class SpreadMonitorProtocol(Protocol):
    """Protocol describing the spread monitor interactions used in tests."""

    cooldown_state: SpreadCooldownState

    def update(self, spread_frame: Any) -> SpreadCooldownState:
        """Ingest the latest spread metrics and update the cooldown state."""

    def current_snapshot(self) -> SpreadSnapshot:
        """Return the latest spread snapshot for observability hooks."""


__all__ = [
    "SpreadCooldownState",
    "SpreadDataDegraded",
    "SpreadMonitorProtocol",
    "SpreadSnapshot",
]
