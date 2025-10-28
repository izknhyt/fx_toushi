"""Stub for the `tradectl spread` command (see §17.7)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["inspect"]


def inspect(
    symbol: str,
    *,
    window: str,
    percentile: int = 95,
    fail_on_gap: bool = False,
    export: str | None = None,
) -> dict[str, object]:
    """Inspect spread metrics (stub)."""

    logger.info(
        "cli.spread.inspect.stub",
        extra={
            "symbol": symbol,
            "window": window,
            "percentile": percentile,
            "fail_on_gap": fail_on_gap,
            "export": export,
        },
    )
    raise NotImplementedError("tradectl spread is not implemented in the M1 scaffold")
