"""Stub for the `tradectl status` command (see §17.3)."""

from __future__ import annotations

import logging
from typing import Mapping

logger = logging.getLogger(__name__)

__all__ = ["status"]


def status(
    *,
    verbose: bool = False,
    json_output: bool = False,
    ack: str | None = None,
    kill_switch: str | None = None,
    board: str | None = None,
) -> Mapping[str, object]:
    """Return the current status snapshot (stub)."""

    logger.info(
        "cli.status.stub",
        extra={
            "verbose": verbose,
            "json": json_output,
            "ack": ack,
            "kill_switch": kill_switch,
            "board": board,
        },
    )
    raise NotImplementedError("tradectl status is not implemented in the M1 scaffold")
