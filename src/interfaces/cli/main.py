"""Executable entrypoint for the ``tradectl`` Typer application."""

from __future__ import annotations

import typer

from . import create_cli_app

app = create_cli_app()


def main() -> None:
    """Execute the CLI application."""

    app()


if __name__ == "__main__":  # pragma: no cover - manual execution guard
    typer.run(main)
