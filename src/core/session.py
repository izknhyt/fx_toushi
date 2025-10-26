"""Session lifecycle management primitives.

This module defines the contracts that orchestrate the
lifecycle of a trading session. The abstractions capture how the
application coordinates configuration, telemetry, and workflow
activation so that downstream components can remain deterministic
and mode-aware.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@dataclass(slots=True)
class SessionConfig:
    """Configuration envelope for orchestrating a trading session.

    The structure stores the execution mode and optional snapshot
    recovery hints that will be surfaced to orchestrators. Concrete
    implementations are expected to enrich this payload with
    milestone-specific settings as they come online.
    """

    mode: str
    telemetry_enabled: bool = True
    snapshot_path: Optional[str] = None


@dataclass(slots=True)
class SessionContext:
    """Runtime state that is passed into workflows at session start.

    The context object maintains identifiers and feature toggles that
    help downstream pipelines adapt to Backtest, Paper, or Live
    execution environments without leaking implementation details.
    """

    session_id: str
    mode: str
    feature_flags: Optional[dict[str, bool]] = None


@runtime_checkable
class SessionManager(Protocol):
    """Protocol defining the responsibilities for managing a session.

    Concrete managers coordinate workflow registration, snapshot
    recovery, and health reporting. Implementations should remain pure
    and side-effect free until :meth:`start` is invoked.
    """

    config: SessionConfig

    def start(self, context: SessionContext) -> None:
        """Begin a session with the supplied context."""

    def stop(self) -> None:
        """Stop the session and release any allocated resources."""

    def request_snapshot(self) -> Optional[str]:
        """Return a snapshot identifier if persistence should occur."""
