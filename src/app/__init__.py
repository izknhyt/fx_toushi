"""Application bootstrap utilities for the trading tool."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["bootstrap"]


def bootstrap(*, enable_cli: bool = True) -> Any:
    """Prepare the application runtime once the bootstrap feature flag is enabled."""

    # Feature Flag: feature.app.bootstrap (M1.1+) toggles the full runtime startup path.
    logger.info(
        "bootstrap noop executed (feature.app.bootstrap disabled, enable_cli=%s)",
        enable_cli,
    )
    pass
