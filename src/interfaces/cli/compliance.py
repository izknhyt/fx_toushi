"""Stub for `tradectl compliance` commands (see §17.12)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["status", "ack", "refresh"]


def status(*, json_output: bool = False) -> dict[str, object]:
    """Stub for compliance status inspection."""

    logger.info("cli.compliance.status.stub", extra={"json": json_output})
    raise NotImplementedError("tradectl compliance status is not implemented in the M1 scaffold")


def ack(*, note: str, user: str | None = None, force: bool = False) -> None:
    """Stub for acknowledging risk disclosure."""

    logger.info(
        "cli.compliance.ack.stub",
        extra={"note": note, "user": user, "force": force},
    )
    raise NotImplementedError("tradectl compliance ack is not implemented in the M1 scaffold")


def refresh() -> None:
    """Stub for refreshing compliance state."""

    logger.info("cli.compliance.refresh.stub")
    raise NotImplementedError("tradectl compliance refresh is not implemented in the M1 scaffold")
