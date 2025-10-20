"""Console interface for the FX Operations simulation MVP game."""

from __future__ import annotations

import argparse
from textwrap import dedent
from typing import Iterable

from .config import DEFAULT_CONFIG, GameConfig
from .engine import ActionResult, GameEngine
from .models import GameEvent, Outcome, Stats


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI entry point."""

    parser = argparse.ArgumentParser(
        prog="tradectl-game",
        description="Play the FX Operations HITL simulation MVP.",
    )
    parser.add_argument("--days", type=int, default=DEFAULT_CONFIG.days, help="Number of days to simulate (>=3).")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible runs. Defaults to the configuration seed.",
    )
    return parser


def _format_stats(stats: Stats) -> str:
    return dedent(
        f"""
        Data Quality : {stats.data_quality:>3}
        Risk Load    : {stats.risk_load:>3}
        Team Morale  : {stats.team_morale:>3}
        Profit Score : {stats.profit_score:>3}
        """
    ).strip()


def _print_timeline(events: Iterable[GameEvent]) -> None:
    for event in events:
        delta = event.delta.as_dict()
        delta_text = ", ".join(f"{k} {v:+}" for k, v in delta.items() if v)
        if not delta_text:
            delta_text = "no change"
        print(f"- [{event.category.upper()}] {event.name}: {event.narrative} ({delta_text})")


def _report_outcome(engine: GameEngine) -> None:
    print("\n=== Campaign Complete ===")
    outcome = engine.outcome
    if outcome is Outcome.WON:
        print("You steered the program through the sprint and hit the launch KPIs!")
    elif outcome is Outcome.NEUTRAL:
        print("The sprint ended without disaster, but more iteration is needed to hit launch KPIs.")
    elif outcome is Outcome.LOST:
        print("Operational pressures overwhelmed the team. Review the log and try again.")
    else:
        print("The campaign ended prematurely.")
    print("\nFinal KPIs:")
    print(_format_stats(engine.state.stats))
    print("\nTimeline:")
    _print_timeline(engine.state.timeline)


def _intro(engine: GameEngine) -> None:
    print("=== FX HITL Operations Simulation ===")
    print(
        "Balance data quality, risk, morale, and profit across a sprint inspired by the M1 Core release."
    )
    day_event = engine.consume_day_event()
    if day_event:
        print("\nDay 1 incident:")
        _print_timeline([day_event])


def _prompt_action(engine: GameEngine) -> str:
    actions = list(engine.available_actions())
    print(f"\nDay {engine.state.day} — {engine.current_phase_name()}")
    print(_format_stats(engine.state.stats))
    print("\nAvailable actions:")
    for index, action in enumerate(actions, start=1):
        print(f"  {index}. {action.title} — {action.description}")
    while True:
        choice = input("Select an action (number): ").strip()
        if not choice.isdigit():
            print("Please enter a number from the list.")
            continue
        index = int(choice)
        if 1 <= index <= len(actions):
            return actions[index - 1].key
        print("Invalid selection. Try again.")


def _handle_action(engine: GameEngine, result: ActionResult) -> None:
    print(f"\nResult: {result.event.narrative}")
    delta_text = ", ".join(
        f"{k} {v:+}" for k, v in result.event.delta.as_dict().items() if v
    ) or "no change"
    print(f"Impact: {delta_text}")
    if result.new_day_event:
        print(f"\nDay {engine.state.day} incident:")
        _print_timeline([result.new_day_event])


def run_cli(config: GameConfig, days: int, seed: int | None) -> None:
    if days != config.days:
        config = GameConfig(
            days=days,
            phases=config.phases,
            initial_stats=config.initial_stats.copy(),
            min_data_quality=config.min_data_quality,
            max_risk_load=config.max_risk_load,
            min_team_morale=config.min_team_morale,
            min_profit_score=config.min_profit_score,
            target_profit_score=config.target_profit_score,
            min_successful_data_quality=config.min_successful_data_quality,
            min_successful_team_morale=config.min_successful_team_morale,
            max_successful_risk_load=config.max_successful_risk_load,
            seed=config.seed if seed is None else seed,
        )
    engine = GameEngine(config, seed=seed)
    _intro(engine)
    while engine.outcome is Outcome.ONGOING:
        action_key = _prompt_action(engine)
        result = engine.apply_action(action_key)
        _handle_action(engine, result)
    _report_outcome(engine)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.days < 3:
        parser.error("--days must be at least 3")
    run_cli(DEFAULT_CONFIG, days=args.days, seed=args.seed)


if __name__ == "__main__":  # pragma: no cover - entry point
    main()
