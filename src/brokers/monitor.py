"""Broker monitor stub."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class BrokerMonitor:
    def heartbeat(self) -> None:
        logger.info("broker.monitor.heartbeat")


__all__ = ["BrokerMonitor"]
