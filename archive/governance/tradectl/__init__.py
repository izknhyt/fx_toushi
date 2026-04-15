"""Module entrypoints so that ``python -m tradectl`` delegates to the Typer CLI."""

from __future__ import annotations

from src.interfaces.cli import create_cli_app

_APP = create_cli_app()


def main() -> None:
    """Delegate execution to the Typer application used by ``tradectl``."""

    _APP()


__all__ = ["main"]
