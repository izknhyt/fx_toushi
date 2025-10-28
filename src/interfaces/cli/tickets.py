"""Stubs for `tradectl ticket` subcommands (see §17.2)."""

from __future__ import annotations

import logging
from typing import Mapping

logger = logging.getLogger(__name__)

__all__ = ["approve", "reject", "edit", "list_tickets", "list"]


def approve(ticket_id: str, *, note: str | None = None, user: str | None = None, force_consent: bool = False) -> None:
    """Stub for approving a ticket."""

    logger.info(
        "cli.ticket.approve.stub",
        extra={"ticket_id": ticket_id, "note": note, "user": user, "force_consent": force_consent},
    )
    raise NotImplementedError("ticket approval CLI is not implemented in the M1 scaffold")


def reject(ticket_id: str, *, reason: str | None = None) -> None:
    """Stub for rejecting a ticket."""

    logger.info("cli.ticket.reject.stub", extra={"ticket_id": ticket_id, "reason": reason})
    raise NotImplementedError("ticket rejection CLI is not implemented in the M1 scaffold")


def edit(ticket_id: str, *, field: str, value: str) -> None:
    """Stub for editing ticket attributes."""

    logger.info(
        "cli.ticket.edit.stub",
        extra={"ticket_id": ticket_id, "field": field, "value": value},
    )
    raise NotImplementedError("ticket edit CLI is not implemented in the M1 scaffold")


def list_tickets(*, status: str | None = None, include_history: bool = False, json_output: bool = False) -> list[Mapping[str, object]]:
    """Stub for listing tickets."""

    logger.info(
        "cli.ticket.list.stub",
        extra={"status": status, "include_history": include_history, "json": json_output},
    )
    raise NotImplementedError("ticket listing CLI is not implemented in the M1 scaffold")


# Alias maintained for Typer command registration parity.
list = list_tickets  # type: ignore[assignment]
