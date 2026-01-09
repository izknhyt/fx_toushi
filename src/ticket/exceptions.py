"""Ticket builder specific exception types."""

from __future__ import annotations

from collections.abc import Mapping


class TicketError(Exception):
    """Base class for ticket generation errors."""


class TicketBlockedError(TicketError):
    """Raised when the gate state prevents a ticket from being issued."""

    def __init__(
        self, *, code: str, message: str, details: Mapping[str, object] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


class ChecklistInvariantError(TicketError):
    """Raised when the checklist definition is violated."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
