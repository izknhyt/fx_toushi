"""Tests covering event guard behaviour and selection logic."""

from __future__ import annotations

from random import Random

from tradectl_game.events import INCIDENTS, Incident, pick_incident
from tradectl_game.models import GameState, StatDelta, Stats


def build_state(**overrides: int) -> GameState:
    stats = Stats(
        data_quality=overrides.get("data_quality", 60),
        risk_load=overrides.get("risk_load", 45),
        team_morale=overrides.get("team_morale", 55),
        profit_score=overrides.get("profit_score", 0),
    )
    return GameState(day=1, phase_index=0, stats=stats)


def test_incident_guard_blocks_when_condition_not_met() -> None:
    incident = Incident(
        name="Morale Boost",
        description="A surprise bonus lifts spirits.",
        delta_factory=lambda state: StatDelta(team_morale=5),
        guard=lambda state: state.stats.team_morale < 80,
    )
    state = build_state(team_morale=95)
    assert incident.applies(state) is False


def test_pick_incident_falls_back_to_quiet(monkeypatch) -> None:
    state = build_state()

    def _never(_: GameState) -> bool:
        return False

    muted_incidents = (
        Incident("A", "", lambda _: StatDelta(), guard=_never),
        Incident("B", "", lambda _: StatDelta(), guard=_never),
    )
    monkeypatch.setattr("tradectl_game.events.INCIDENTS", muted_incidents)
    event = pick_incident(state, Random(1))
    assert event.name == "Quiet Morning"
    assert event.category == "incident"
    assert event.delta.as_dict() == {"data_quality": 0, "risk_load": 0, "team_morale": 0, "profit_score": 0}


def test_default_incidents_all_have_guards() -> None:
    for incident in INCIDENTS:
        assert incident.guard is not None
