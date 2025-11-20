"""Shared rendering helpers for CLI modules (see §1.3)."""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from rich.console import Console
from rich.table import Table

_console = Console()


def render_key_values(items: Mapping[str, object], *, title: str | None = None) -> None:
    """Render a key/value table via Rich for consistent CLI UX."""

    table = Table(title=title or "details")
    table.add_column("key", style="bold")
    table.add_column("value")
    for key, value in items.items():
        table.add_row(str(key), "-" if value is None else str(value))
    _console.print(table)


def render_table(rows: Iterable[Sequence[object]], headers: Sequence[str], *, title: str | None = None) -> None:
    """Render an arbitrary table with the supplied headers."""

    table = Table(title=title)
    for header in headers:
        table.add_column(str(header))
    for row in rows:
        table.add_row(*[str(cell) for cell in row])
    _console.print(table)


__all__ = ["render_key_values", "render_table"]
