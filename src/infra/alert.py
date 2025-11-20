"""Alert dispatcher stub."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class AlertDispatcher:
    def dispatch(self, *, level: str, message: str) -> None:
        logger.log(getattr(logging, level.upper(), logging.INFO), message)


__all__ = ["AlertDispatcher"]
