"""CLI entrypoints for the `tradectl` operator tooling."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["create_cli_app"]


def create_cli_app() -> Any:
    """Return the root Typer application once the CLI feature flag enables it."""

    # Feature Flag: feature.cli.operator_tools (M1.1+) gates the interactive CLI rollout.
    logger.info(
        "create_cli_app noop executed because feature.cli.operator_tools remains disabled for M1 core",
    )
    pass
