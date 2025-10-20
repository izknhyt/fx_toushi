"""Random event definitions for the FX Operations simulation game."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Callable, Sequence

from .models import GameEvent, GameState, StatDelta


@dataclass(frozen=True)
class Incident:
    """Random day-opening incident that affects the campaign."""

    name: str
    description: str
    delta_factory: Callable[[GameState], StatDelta]
    guard: Callable[[GameState], bool] | None = None

    def applies(self, state: GameState) -> bool:
        """Return ``True`` if the incident should be considered for the state."""

        return self.guard(state) if self.guard else True

    def trigger(self, state: GameState) -> GameEvent:
        """Generate the event narrative and delta for the supplied state."""

        delta = self.delta_factory(state)
        return GameEvent("incident", self.name, self.description, delta)


def _incident_catalogue() -> Sequence[Incident]:
    def data_feed_outage(state: GameState) -> StatDelta:
        penalty = -12 if state.stats.data_quality > 35 else -8
        return StatDelta(data_quality=penalty, risk_load=5)

    def market_tailwind(_: GameState) -> StatDelta:
        return StatDelta(profit_score=10, risk_load=4)

    def morale_break(state: GameState) -> StatDelta:
        penalty = -9 if state.stats.team_morale > 40 else -6
        return StatDelta(team_morale=penalty, data_quality=-2)

    def clean_run(state: GameState) -> StatDelta:
        bonus = 6 if state.stats.data_quality < 85 else 3
        morale = 4 if state.stats.team_morale < 80 else 2
        return StatDelta(data_quality=bonus, team_morale=morale)

    def audit_ping(state: GameState) -> StatDelta:
        risk_penalty = 6 if state.stats.risk_load < 70 else 3
        return StatDelta(risk_load=risk_penalty, profit_score=-4)

    incidents = (
        Incident(
            name="Data Feed Lag",
            description="Overnight fetch retries slowed to a crawl.",
            delta_factory=data_feed_outage,
        ),
        Incident(
            name="Market Tailwind",
            description="Carry trades rally across the board, boosting upside.",
            delta_factory=market_tailwind,
        ),
        Incident(
            name="Ops Fatigue",
            description="Long hours catch up with the rotation schedule.",
            delta_factory=morale_break,
        ),
        Incident(
            name="Smooth Sync",
            description="Ingestion finishes with perfect parity checks.",
            delta_factory=clean_run,
        ),
        Incident(
            name="Audit Follow-up",
            description="Compliance calls for a deep dive on exposure changes.",
            delta_factory=audit_ping,
        ),
    )
    return incidents


INCIDENTS: Sequence[Incident] = _incident_catalogue()


def pick_incident(state: GameState, rng: Random) -> GameEvent:
    """Pick and trigger a random applicable incident for the day."""

    candidates = [incident for incident in INCIDENTS if incident.applies(state)]
    if not candidates:
        return GameEvent("incident", "Quiet Morning", "No notable incidents occurred.", StatDelta())
    incident = rng.choice(candidates)
    return incident.trigger(state)


__all__ = ["Incident", "pick_incident", "INCIDENTS"]
