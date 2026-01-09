"""Application entry point wrapper aligning with §1.3."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from tradectl import main as tradectl_main

logger = logging.getLogger(__name__)


def run(argv: Sequence[str] | None = None) -> None:
    """Bootstrap the Typer CLI that powers ``tradectl`` commands."""

    if argv:
        import sys

        sys.argv = [sys.argv[0], *[str(arg) for arg in argv]]
        logger.debug("app.main.run.override_argv", extra={"argv": list(argv)})
    tradectl_main()


__all__ = ["run"]
