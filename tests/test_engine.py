from tradectl_game.config import DEFAULT_CONFIG, GameConfig
from tradectl_game.engine import GameEngine, Outcome


def build_engine(seed: int = 1) -> GameEngine:
    return GameEngine(DEFAULT_CONFIG, seed=seed)


def test_action_application_updates_stats():
    engine = build_engine()
    initial_quality = engine.state.stats.data_quality
    result = engine.apply_action("catch_up")
    assert result.event.delta.data_quality >= 0
    assert engine.state.stats.data_quality >= initial_quality


def test_incident_applies_on_start():
    engine = build_engine(seed=3)
    incident = engine.consume_day_event()
    assert incident is not None
    assert incident.category == "incident"
    delta = incident.delta.as_dict()
    assert set(delta.keys()) == {"data_quality", "risk_load", "team_morale", "profit_score"}


def test_loss_condition_triggers():
    config = DEFAULT_CONFIG
    losing_stats = config.initial_stats.copy()
    losing_stats.data_quality = 0
    custom_config = GameConfig(
        days=config.days,
        phases=config.phases,
        initial_stats=losing_stats,
        min_data_quality=config.min_data_quality,
        max_risk_load=config.max_risk_load,
        min_team_morale=config.min_team_morale,
        min_profit_score=config.min_profit_score,
        target_profit_score=config.target_profit_score,
        min_successful_data_quality=config.min_successful_data_quality,
        min_successful_team_morale=config.min_successful_team_morale,
        max_successful_risk_load=config.max_successful_risk_load,
        seed=config.seed,
    )
    engine = GameEngine(custom_config, seed=5)
    assert engine.outcome is Outcome.LOST


def test_win_condition_met_after_final_day():
    engine = GameEngine(DEFAULT_CONFIG, seed=2)
    engine.state.stats.data_quality = 90
    engine.state.stats.team_morale = 90
    engine.state.stats.risk_load = 20
    engine.state.stats.profit_score = 60
    engine.state.day = engine.state.day + DEFAULT_CONFIG.days
    outcome = engine._evaluate_outcome(final_check=True)
    assert outcome is Outcome.WON
