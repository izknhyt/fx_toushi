"""API failover stub."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ApiFailoverPlanner:
    def trigger(self, reason: str) -> None:
        logger.warning("broker.failover.trigger", extra={"reason": reason})


__all__ = ["ApiFailoverPlanner"]
