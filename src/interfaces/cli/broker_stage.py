"""Stub for `tradectl broker stage` commands."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["stage_status", "stage_set", "stage_history"]


def stage_status(*, json_output: bool = False) -> dict[str, object]:
    """Stub for querying broker autonomy stages."""

    logger.info("cli.broker.stage.status.stub", extra={"json": json_output})
    raise NotImplementedError("tradectl broker stage status is not implemented in the M1 scaffold")


def stage_set(*, request: str, approve: str | None = None) -> None:
    """Stub for requesting/approving stage transitions."""

    logger.info(
        "cli.broker.stage.set.stub",
        extra={"request": request, "approve": approve},
    )
    raise NotImplementedError("tradectl broker stage set is not implemented in the M1 scaffold")


def stage_history(*, limit: int = 20) -> list[dict[str, object]]:
    """Stub for reviewing stage history."""

    logger.info("cli.broker.stage.history.stub", extra={"limit": limit})
    raise NotImplementedError("tradectl broker stage history is not implemented in the M1 scaffold")
