"""Action definitions for the FX Operations simulation game."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from .models import GameEvent, GameState, StatDelta


ActionExecutor = Callable[[GameState], GameEvent]


@dataclass(frozen=True)
class Action:
    """Action that the player may choose during a phase."""

    key: str
    title: str
    description: str
    executor: ActionExecutor

    def execute(self, state: GameState) -> GameEvent:
        """Execute the action and return the resulting event."""

        return self.executor(state)


def clamp_bonus(value: int, current: int, upper: int) -> int:
    """Clamp a positive bonus so stats do not exceed their upper bound."""

    return max(0, min(value, upper - current))


def build_actions() -> Mapping[str, Action]:
    """Build the catalog of actions keyed by identifier."""

    def catch_up_executor(state: GameState) -> GameEvent:
        bonus = clamp_bonus(12, state.stats.data_quality, 100)
        delta = StatDelta(data_quality=bonus, team_morale=-4)
        narrative = (
            "You lead an early catch-up sprint. Data ingestion stabilises but the team is a little tired."
        )
        return GameEvent("action", "Run Catch-up", narrative, delta)

    def approve_signal_executor(state: GameState) -> GameEvent:
        delta = StatDelta(data_quality=-5, risk_load=8, profit_score=12)
        narrative = (
            "You green-light the top-performing signal bundle. Profit potential rises along with exposure."
        )
        return GameEvent("action", "Approve Signals", narrative, delta)

    def tighten_risk_executor(state: GameState) -> GameEvent:
        penalty = -6 if state.stats.profit_score > 10 else -3
        delta = StatDelta(risk_load=-14, profit_score=penalty)
        narrative = (
            "You tighten position limits and review stops. Risk load drops, though potential gains shrink."
        )
        return GameEvent("action", "Tighten Risk", narrative, delta)

    def stabilise_executor(state: GameState) -> GameEvent:
        quality_gain = clamp_bonus(9, state.stats.data_quality, 100)
        delta = StatDelta(data_quality=quality_gain, risk_load=-4, profit_score=-2)
        narrative = (
            "Ops spend extra time validating metrics and resyncing caches. Quality improves and exposure is trimmed."
        )
        return GameEvent("action", "Stabilise Ops", narrative, delta)

    def care_team_executor(state: GameState) -> GameEvent:
        morale_gain = clamp_bonus(11, state.stats.team_morale, 100)
        delta = StatDelta(team_morale=morale_gain, risk_load=3, profit_score=-1)
        narrative = "You run a wellbeing check and rotate duties. Spirits lift but focus shifts away from trades."
        return GameEvent("action", "Team Care", narrative, delta)

    def push_retro_executor(state: GameState) -> GameEvent:
        morale_boost = clamp_bonus(7, state.stats.team_morale, 100)
        delta = StatDelta(team_morale=morale_boost, data_quality=4, profit_score=3)
        narrative = (
            "A fast retrospective uncovers automation wins. Morale climbs and tomorrow's prep gains momentum."
        )
        return GameEvent("action", "Retro & Prep", narrative, delta)

    actions = [
        Action("catch_up", "Run Catch-up", "Stabilise ingestion throughput.", catch_up_executor),
        Action(
            "approve_signal",
            "Approve Signals",
            "Push the most compelling signals to the board.",
            approve_signal_executor,
        ),
        Action(
            "tighten_risk",
            "Tighten Risk",
            "Dial back exposure and reinforce stop discipline.",
            tighten_risk_executor,
        ),
        Action(
            "stabilise",
            "Stabilise Ops",
            "Focus on validation and cache resync workflows.",
            stabilise_executor,
        ),
        Action(
            "care_team",
            "Team Care",
            "Rotate duties and give the team breathing room.",
            care_team_executor,
        ),
        Action(
            "push_retro",
            "Retro & Prep",
            "Hold a rapid retrospective to bank learnings.",
            push_retro_executor,
        ),
    ]
    return {action.key: action for action in actions}


ACTIONS: Mapping[str, Action] = build_actions()

__all__ = ["Action", "ACTIONS", "build_actions"]
