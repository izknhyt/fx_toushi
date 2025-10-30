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

from src.app.mode_context import ModeContext, ModeContextFactory


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
    profile_name: Optional[str] = None
    mode_factory: Optional[ModeContextFactory] = None


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
    mode_context: Optional[ModeContext] = None


@runtime_checkable
class SessionManager(Protocol):
    """Protocol defining the responsibilities for managing a session.

    Concrete managers coordinate workflow registration, snapshot
    recovery, and health reporting. Implementations should remain pure
    and side-effect free until :meth:`start` is invoked.
    """

    config: SessionConfig
    mode_factory: Optional[ModeContextFactory]

    def start(self, context: SessionContext) -> None:
        """Begin a session with the supplied context."""

    def stop(self) -> None:
        """Stop the session and release any allocated resources."""

    def request_snapshot(self) -> Optional[str]:
        """Return a snapshot identifier if persistence should occur."""


def create_session_context(
    *,
    profile_name: str,
    session_id: str,
    config: SessionConfig | None = None,
    factory: ModeContextFactory | None = None,
    feature_flags: Optional[dict[str, bool]] = None,
) -> SessionContext:
    """Create a :class:`SessionContext` populated with a :class:`ModeContext`.

    The helper wires a :class:`ModeContextFactory` into the lightweight
    session scaffolding so that ``tradectl start --profile ...`` scripts can
    exercise deterministic profile bootstraps during validation runs.
    """

    effective_factory = factory or (config.mode_factory if config else None) or ModeContextFactory()
    mode_context = effective_factory.create(profile_name, session_id=session_id)

    if config is not None:
        if config.profile_name is not None and config.profile_name != profile_name:
            raise ValueError(
                f"SessionConfig.profile_name={config.profile_name!r} does not match requested profile {profile_name!r}"
            )
        if config.mode != mode_context.mode:
            raise ValueError(
                "SessionConfig.mode must align with the profile mode ("
                f"expected {mode_context.mode!r}, found {config.mode!r})"
            )

    return SessionContext(
        session_id=session_id,
        mode=mode_context.mode if config is None else config.mode,
        feature_flags=feature_flags,
        mode_context=mode_context,
    )
