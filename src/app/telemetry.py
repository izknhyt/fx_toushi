"""Telemetry bootstrap stub used by CLI/session orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TelemetryConfig:
    """Configuration payload for telemetry initialisation."""

    session_id: str = "interactive"
    reporter: str = "local"
    enabled: bool = True
    tags: Mapping[str, str] = field(default_factory=dict)


def initialise(config: TelemetryConfig | None = None) -> str:
    """Initialise telemetry sinks and return the active session id."""

    cfg = config or TelemetryConfig(
        session_id=f"session-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    )
    if not cfg.enabled:
        logger.info("app.telemetry.disabled", extra={"session_id": cfg.session_id})
        return cfg.session_id

    logger.info(
        "app.telemetry.initialised",
        extra={"session_id": cfg.session_id, "reporter": cfg.reporter, "tags": dict(cfg.tags)},
    )
    return cfg.session_id


__all__ = ["TelemetryConfig", "initialise"]
