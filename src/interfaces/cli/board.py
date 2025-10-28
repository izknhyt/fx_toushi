"""Stubs for the `tradectl board` command group (see §17.1)."""

from __future__ import annotations

import logging
from typing import Iterable, Mapping, Sequence

logger = logging.getLogger(__name__)

__all__ = ["BoardRenderer", "board"]


class BoardRenderer:
    """Placeholder renderer for board ticket output."""

    def render_ticket(self, ticket: Mapping[str, object]) -> str:
        """Format a ticket payload for CLI output (stub)."""

        raise NotImplementedError("BoardRenderer is a stub for future implementation")


def board(
    filters: Sequence[str] | None = None,
    *,
    view: str = "tickets",
    guarded: bool = False,
    normal: bool = False,
    json_output: bool = False,
    include: Iterable[str] | None = None,
) -> None:
    """Entry point stub for `tradectl board`."""

    logger.info(
        "cli.board.stub",  # Consistent logging hook for future instrumentation
        extra={
            "filters": list(filters or ()),
            "view": view,
            "guarded": guarded,
            "normal": normal,
            "json": json_output,
            "include": list(include or ()),
        },
    )
    raise NotImplementedError("tradectl board is not implemented in the M1 scaffold")
