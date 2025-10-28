"""Spread monitoring contracts and type aliases used across the codebase."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping, Protocol, runtime_checkable

from typing_extensions import Literal

SpreadCooldownState = Literal["normal", "watch", "cooldown", "halt"]
"""Spread guard state shared between execution, risk, and strategy layers."""


@dataclass(slots=True, frozen=True)
class SpreadState:
    """Normalized spread state shared with gate aggregation and audit flows."""

    state: SpreadCooldownState
    spread_pips: Decimal
    percentile: float
    threshold_pips: Decimal
    cooldown_eta: datetime | None
    last_updated: datetime
    lookback_window_sec: int


@dataclass(slots=True, frozen=True)
class SpreadSnapshot:
    """Minimal snapshot of spread metrics for a single symbol."""

    symbol: str
    spread_state: SpreadState

    @property
    def cooldown_state(self) -> SpreadCooldownState:
        """Expose the cooldown label for quick checks in diagnostics."""

        return self.spread_state.state


class SpreadDataDegraded(RuntimeError):
    """Raised when spread data quality is insufficient for guard decisions."""


@runtime_checkable
class SpreadMonitorProtocol(Protocol):
    """Protocol describing the spread monitor interactions used in tests."""

    @property
    def cooldown_state(self) -> SpreadCooldownState:
        """Return the aggregate cooldown state across the monitored universe."""

    def update(self, spread_frame: Any) -> SpreadCooldownState:
        """Ingest the latest spread metrics and update the cooldown state."""

    def current_state(
        self, *, symbols: Iterable[str] | None = None
    ) -> Mapping[str, SpreadState]:
        """Return the canonical spread state mapping used by gate/audit flows."""

    def current_snapshot(self) -> SpreadSnapshot:
        """Return the latest per-symbol spread snapshot for observability hooks."""


__all__ = [
    "SpreadCooldownState",
    "SpreadDataDegraded",
    "SpreadMonitorProtocol",
    "SpreadState",
    "SpreadSnapshot",
]
