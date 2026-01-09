"""Scenario dataset registry stub for stress-test flows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ScenarioDataset:
    """Lightweight scenario metadata record."""

    name: str
    path: Path
    description: str | None = None
    kind: str = "shock"
    checksum: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": str(self.path),
            "description": self.description,
            "kind": self.kind,
            "checksum": self.checksum,
        }


class ScenarioDatasetRegistry:
    """In-memory registry to support CLI listing/validation."""

    def __init__(self) -> None:
        self._registry: dict[str, ScenarioDataset] = {}

    def register(self, dataset: ScenarioDataset) -> None:
        self._registry[dataset.name] = dataset

    def list(self) -> list[ScenarioDataset]:
        return list(self._registry.values())

    def get(self, name: str) -> ScenarioDataset:
        if name not in self._registry:
            raise KeyError(f"Scenario '{name}' not registered")
        return self._registry[name]

    def validate(self, *, base_dir: Path | None = None) -> list[dict[str, object]]:
        """Validate registered entries exist on disk and return summaries."""

        summaries: list[dict[str, object]] = []
        for dataset in self._registry.values():
            path = dataset.path
            if base_dir and not path.is_absolute():
                path = base_dir / path
            summaries.append(
                {
                    "name": dataset.name,
                    "exists": path.exists(),
                    "path": str(path),
                    "kind": dataset.kind,
                    "description": dataset.description,
                }
            )
        return summaries

    @classmethod
    def from_mapping(cls, payload: Iterable[Mapping[str, object]]) -> ScenarioDatasetRegistry:
        registry = cls()
        for entry in payload:
            registry.register(
                ScenarioDataset(
                    name=str(entry.get("name")),
                    path=Path(str(entry.get("path"))),
                    description=str(entry.get("description") or "") or None,
                    kind=str(entry.get("kind") or "shock"),
                    checksum=entry.get("checksum") or None,
                )
            )
        return registry
