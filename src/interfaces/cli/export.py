"""Stub module for generic export helpers (see §1.3)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["export_snapshot"]


def export_snapshot(*, destination: str, include_sensitive: bool = False) -> None:
    """Stub for exporting aggregated data snapshots."""

    logger.info(
        "cli.export.snapshot.stub",
        extra={"destination": destination, "include_sensitive": include_sensitive},
    )
    raise NotImplementedError("tradectl export snapshot is not implemented in the M1 scaffold")
