"""Dependency registry stub."""

from __future__ import annotations

from typing import Callable, Dict


class DependencyRegistry:
    def __init__(self) -> None:
        self._factories: Dict[str, Callable[[], object]] = {}

    def register(self, name: str, factory: Callable[[], object]) -> None:
        self._factories[name] = factory

    def resolve(self, name: str) -> object:
        return self._factories[name]()


__all__ = ["DependencyRegistry"]
