from __future__ import annotations

import pytest

from src.infra.registry import DependencyNotFoundError, DependencyRegistry


def test_dependency_registry_singleton() -> None:
    registry = DependencyRegistry()
    registry.register("obj", lambda: object(), singleton=True)
    first = registry.resolve("obj")
    second = registry.resolve("obj")
    assert first is second


def test_dependency_registry_missing_raises() -> None:
    registry = DependencyRegistry()
    with pytest.raises(DependencyNotFoundError):
        registry.resolve("missing")
