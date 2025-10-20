"""Game engine that orchestrates the FX Operations simulation."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Iterable

from .actions import ACTIONS, Action
from .config import GameConfig
from .events import pick_incident
from .models import GameEvent, GameState, Outcome


@dataclass
class ActionResult:
    """Structured response from applying an action."""

    event: GameEvent
    outcome: Outcome
    new_day_event: GameEvent | None = None


class GameEngine:
    """Core orchestration logic for the MVP game."""

    def __init__(self, config: GameConfig, seed: int | None = None):
        self._config = config
        self._rng = Random(seed if seed is not None else config.seed)
        self._state = GameState(day=1, phase_index=0, stats=config.initial_stats.copy())
        self._outcome = Outcome.ONGOING
        self._pending_day_event: GameEvent | None = self._start_day()

    @property
    def state(self) -> GameState:
        """Return the live game state."""

        return self._state

    @property
    def outcome(self) -> Outcome:
        """Return the current outcome status."""

        return self._outcome

    def consume_day_event(self) -> GameEvent | None:
        """Return and clear the pending day-opening event."""

        event = self._pending_day_event
        self._pending_day_event = None
        return event

    def available_actions(self) -> Iterable[Action]:
        """Return the actions available for the current phase."""

        keys = self._config.actions_for_phase(self._state.phase_index)
        return tuple(ACTIONS[key] for key in keys)

    def current_phase_name(self) -> str:
        """Return the human readable name for the current phase."""

        return self._config.phase_names[self._state.phase_index]

    def apply_action(self, action_key: str) -> ActionResult:
        """Apply the requested action and advance the game state."""

        if self._outcome is not Outcome.ONGOING:
            raise RuntimeError("Cannot apply action when game has finished")

        if action_key not in ACTIONS:
            raise KeyError(f"Unknown action: {action_key}")

        allowed = self._config.actions_for_phase(self._state.phase_index)
        if action_key not in allowed:
            raise ValueError(f"Action '{action_key}' is not permitted during this phase")

        action = ACTIONS[action_key]
        event = action.execute(self._state)
        self._state.stats.apply(event.delta)
        self._state.record_event(event)
        self._outcome = self._evaluate_outcome()

        new_day_event = None
        if self._outcome is Outcome.ONGOING:
            self._advance_phase()
            if self._state.phase_index == 0:
                new_day_event = self._start_day()
        return ActionResult(event=event, outcome=self._outcome, new_day_event=new_day_event)

    def _advance_phase(self) -> None:
        phase_count = len(self._config.phases)
        self._state.phase_index += 1
        if self._state.phase_index >= phase_count:
            self._state.phase_index = 0
            self._state.day += 1

    def _start_day(self) -> GameEvent | None:
        if self._state.day > self._config.days:
            self._outcome = self._evaluate_outcome(final_check=True)
            return None
        event = pick_incident(self._state, self._rng)
        self._state.stats.apply(event.delta)
        self._state.record_event(event)
        self._outcome = self._evaluate_outcome()
        return event

    def _evaluate_outcome(self, final_check: bool = False) -> Outcome:
        stats = self._state.stats
        if stats.data_quality < self._config.min_data_quality:
            return Outcome.LOST
        if stats.team_morale < self._config.min_team_morale:
            return Outcome.LOST
        if stats.risk_load >= self._config.max_risk_load:
            return Outcome.LOST
        if stats.profit_score < self._config.min_profit_score:
            return Outcome.LOST

        if final_check or self._state.day > self._config.days:
            if (
                stats.profit_score >= self._config.target_profit_score
                and stats.data_quality >= self._config.min_successful_data_quality
                and stats.team_morale >= self._config.min_successful_team_morale
                and stats.risk_load < self._config.max_successful_risk_load
            ):
                return Outcome.WON
            return Outcome.NEUTRAL

        return Outcome.ONGOING


__all__ = ["GameEngine", "ActionResult"]
