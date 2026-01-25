"""Dependency registry with optional singleton caching."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class DependencyNotFoundError(RuntimeError):
    """Raised when a dependency is not registered."""


@dataclass(slots=True)
class RegistryEntry:
    factory: Callable[[], object]
    singleton: bool
    instance: object | None = None


class DependencyRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}

    def register(self, name: str, factory: Callable[[], object], *, singleton: bool = True) -> None:
        self._entries[name] = RegistryEntry(factory=factory, singleton=singleton)

    def register_instance(self, name: str, instance: object) -> None:
        self._entries[name] = RegistryEntry(factory=lambda: instance, singleton=True, instance=instance)

    def resolve(self, name: str) -> object:
        if name not in self._entries:
            raise DependencyNotFoundError(name)
        entry = self._entries[name]
        if entry.singleton:
            if entry.instance is None:
                entry.instance = entry.factory()
            return entry.instance
        return entry.factory()

    def has(self, name: str) -> bool:
        return name in self._entries

    def list(self) -> list[str]:
        return sorted(self._entries.keys())

    def reset(self, name: str | None = None) -> None:
        if name is None:
            for entry in self._entries.values():
                entry.instance = None
            return
        if name in self._entries:
            self._entries[name].instance = None


__all__ = ["DependencyNotFoundError", "DependencyRegistry", "RegistryEntry"]
