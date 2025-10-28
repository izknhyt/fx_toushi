"""Generic event stream CLI stubs (directory scaffold, see §1.3)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["tail_events"]


def tail_events(*, since: str | None = None, follow: bool = False) -> list[dict[str, object]]:
    """Stub for streaming domain events."""

    logger.info("cli.events.tail.stub", extra={"since": since, "follow": follow})
    raise NotImplementedError("tradectl events tail is not implemented in the M1 scaffold")
