"""Configuration objects for the FX Operations simulation game."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .models import Stats


@dataclass(frozen=True)
class PhaseConfig:
    """Represents a single daily phase in the game loop."""

    name: str
    """Human readable name (e.g. ``"Morning Ops"``)."""

    action_keys: Sequence[str]
    """Identifiers for actions that are valid during the phase."""


@dataclass(frozen=True)
class GameConfig:
    """Top level configuration for a campaign."""

    days: int
    phases: Sequence[PhaseConfig]
    initial_stats: Stats
    min_data_quality: int
    max_risk_load: int
    min_team_morale: int
    min_profit_score: int
    target_profit_score: int
    min_successful_data_quality: int
    min_successful_team_morale: int
    max_successful_risk_load: int
    seed: int = 7

    def __post_init__(self) -> None:  # type: ignore[override]
        if self.days < 3:
            raise ValueError("days must be >= 3 for a meaningful campaign")
        if not self.phases:
            raise ValueError("at least one phase must be configured")
        if any(not phase.action_keys for phase in self.phases):
            raise ValueError("each phase must expose at least one action")

    @property
    def phase_names(self) -> tuple[str, ...]:
        """Return the ordered phase names for reference."""

        return tuple(phase.name for phase in self.phases)

    def actions_for_phase(self, phase_index: int) -> Sequence[str]:
        """Return the action keys permitted in the supplied phase."""

        return self.phases[phase_index].action_keys


def _default_phases() -> tuple[PhaseConfig, ...]:
    return (
        PhaseConfig(name="Morning Ops", action_keys=("catch_up", "stabilise", "care_team")),
        PhaseConfig(name="Midday Trading", action_keys=("approve_signal", "tighten_risk", "care_team")),
        PhaseConfig(name="Evening Review", action_keys=("stabilise", "care_team", "push_retro")),
    )


def default_stats() -> Stats:
    """Return the baseline statistics for a new campaign."""

    return Stats(data_quality=60, risk_load=45, team_morale=55, profit_score=0)


DEFAULT_CONFIG = GameConfig(
    days=7,
    phases=_default_phases(),
    initial_stats=default_stats(),
    min_data_quality=20,
    max_risk_load=90,
    min_team_morale=15,
    min_profit_score=-30,
    target_profit_score=40,
    min_successful_data_quality=40,
    min_successful_team_morale=35,
    max_successful_risk_load=80,
    seed=11,
)

__all__ = ["PhaseConfig", "GameConfig", "DEFAULT_CONFIG", "default_stats"]
