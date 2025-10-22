"""Domain models shared across the game engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Mapping


@dataclass
class StatDelta:
    """Represents a change across the tracked KPI metrics."""

    data_quality: int = 0
    risk_load: int = 0
    team_morale: int = 0
    profit_score: int = 0

    def as_dict(self) -> Dict[str, int]:
        """Return the delta as a dictionary for reporting."""

        return {
            "data_quality": self.data_quality,
            "risk_load": self.risk_load,
            "team_morale": self.team_morale,
            "profit_score": self.profit_score,
        }

    def is_empty(self) -> bool:
        """Return ``True`` if all deltas are zero."""

        return not any(self.as_dict().values())


@dataclass
class Stats:
    """Game KPIs that evolve during the campaign."""

    data_quality: int
    risk_load: int
    team_morale: int
    profit_score: int

    _bounds: Mapping[str, tuple[int | None, int | None]] = field(
        default_factory=lambda: {
            "data_quality": (0, 100),
            "risk_load": (0, 100),
            "team_morale": (0, 100),
            "profit_score": (None, None),
        }
    )

    def apply(self, delta: StatDelta) -> None:
        """Mutate the stats by applying the supplied delta."""

        for key, change in delta.as_dict().items():
            current = getattr(self, key)
            updated = current + change
            lower, upper = self._bounds[key]
            if lower is not None:
                updated = max(lower, updated)
            if upper is not None:
                updated = min(upper, updated)
            setattr(self, key, updated)

    def copy(self) -> "Stats":
        """Return a shallow copy of the stats."""

        return Stats(
            data_quality=self.data_quality,
            risk_load=self.risk_load,
            team_morale=self.team_morale,
            profit_score=self.profit_score,
        )


@dataclass
class GameEvent:
    """Narrative entry representing either an action or an incident."""

    category: str
    name: str
    narrative: str
    delta: StatDelta


@dataclass
class GameState:
    """Snapshot of the current campaign progression."""

    day: int
    phase_index: int
    stats: Stats
    timeline: List[GameEvent] = field(default_factory=list)

    def phase_number(self) -> int:
        """Return the human friendly (1-based) phase number."""

        return self.phase_index + 1

    def record_event(self, event: GameEvent) -> None:
        """Append the supplied event to the timeline."""

        self.timeline.append(event)


class Outcome(Enum):
    """Possible campaign outcomes."""

    ONGOING = auto()
    WON = auto()
    LOST = auto()
    NEUTRAL = auto()

