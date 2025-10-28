"""Stub for `tradectl audit` commands (see §17.13)."""

from __future__ import annotations

import logging
from typing import Iterable

logger = logging.getLogger(__name__)

__all__ = ["tail", "export"]


def tail(
    *,
    since: str,
    event: Iterable[str] | None = None,
    json_output: bool = False,
) -> list[dict[str, object]]:
    """Stub for audit log tailing."""

    logger.info(
        "cli.audit.tail.stub",
        extra={"since": since, "event": list(event or ()), "json": json_output},
    )
    raise NotImplementedError("tradectl audit tail is not implemented in the M1 scaffold")


def export(
    *,
    export_type: str,
    date_from: str,
    date_to: str,
    out: str,
) -> str:
    """Stub for audit export functionality."""

    logger.info(
        "cli.audit.export.stub",
        extra={"type": export_type, "from": date_from, "to": date_to, "out": out},
    )
    raise NotImplementedError("tradectl audit export is not implemented in the M1 scaffold")
