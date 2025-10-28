"""Stub for `tradectl metrics report` (see §17.8)."""

from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)

__all__ = ["report"]


MetricsKind = Literal["sla", "latency", "pipeline", "ops"]


def report(
    *,
    kind: MetricsKind,
    window: str | None = None,
    mode: str | None = None,
    out: str | None = None,
    validate: bool = False,
) -> str:
    """Render metrics reports (stub)."""

    logger.info(
        "cli.metrics.report.stub",
        extra={
            "kind": kind,
            "window": window,
            "mode": mode,
            "out": out,
            "validate": validate,
        },
    )
    raise NotImplementedError("tradectl metrics report is not implemented in the M1 scaffold")
