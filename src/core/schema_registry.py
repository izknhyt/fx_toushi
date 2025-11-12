"""Helpers for building JSON Schema registries with `referencing`."""

from __future__ import annotations

import json
from pathlib import Path

from referencing import Registry, Resource

__all__ = ["build_schema_registry"]

_FALLBACK_HOST = "https://fx-toushi.dev/schemas"


def _schema_identifiers(candidate: Path, schema_id: str | None) -> set[str]:
    identifiers = {
        candidate.resolve().as_uri(),
        f"{_FALLBACK_HOST}/{candidate.name}",
    }
    if schema_id:
        identifiers.add(schema_id)
    return identifiers


def build_schema_registry(schema_path: Path) -> Registry:
    """Return a `referencing.Registry` seeded with peer schema files."""

    resources: list[tuple[str, Resource]] = []

    for candidate in schema_path.parent.glob("*.schema.json"):
        try:
            contents = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        resource = Resource.from_contents(contents)
        schema_id = contents.get("$id")
        for identifier in _schema_identifiers(candidate, schema_id):
            resources.append((identifier, resource))

    registry = Registry().with_resources(resources)
    return registry
