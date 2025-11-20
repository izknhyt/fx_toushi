"""Autonomy stage guard stub."""

from __future__ import annotations


class AutonomyStageGuard:
    def __init__(self, stage: str = "manual") -> None:
        self.stage = stage

    def promote(self, stage: str) -> None:
        self.stage = stage


__all__ = ["AutonomyStageGuard"]
