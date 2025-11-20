"""Sandbox adapter stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SandboxBridge:
    name: str = "paper"

    def submit(self, payload: dict[str, object]) -> dict[str, object]:
        return payload


__all__ = ["SandboxBridge"]
