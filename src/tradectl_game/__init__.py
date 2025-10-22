"""Core package for the FX Operations simulation MVP game."""

from .config import DEFAULT_CONFIG, GameConfig, PhaseConfig
from .engine import GameEngine, Outcome
from .models import GameEvent, GameState, Stats

__all__ = [
    "DEFAULT_CONFIG",
    "GameConfig",
    "PhaseConfig",
    "GameEngine",
    "Outcome",
    "GameEvent",
    "GameState",
    "Stats",
]
