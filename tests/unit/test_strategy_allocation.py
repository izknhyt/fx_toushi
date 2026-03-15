from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.strategies.allocation import (
    AllocationActivePosition,
    AllocationCandidate,
    AllocationContext,
    StrategyAllocationPolicy,
)


@dataclass(frozen=True, slots=True)
class _Signal:
    strategy_id: str
    symbol: str
    direction: str
    score: float
    confidence: float = 0.0
    quality_score: float = 0.0


def _candidate(
    *,
    strategy_id: str,
    score: float,
    symbol: str = "USDJPY",
    direction: str = "long",
    priority: int = 10,
    weight: float = 1.0,
    spread: float = 0.002,
    slippage: float = 0.001,
) -> AllocationCandidate:
    return AllocationCandidate(
        strategy_id=strategy_id,
        signal=_Signal(
            strategy_id=strategy_id,
            symbol=symbol,
            direction=direction,
            score=score,
            confidence=score,
            quality_score=score,
        ),
        priority=priority,
        weight=weight,
        parameters={"execution": {"spread": spread, "slippage": slippage}},
    )


def _position(
    *,
    strategy_id: str = "open_strat",
    symbol: str = "USDJPY",
    direction: str = "long",
) -> AllocationActivePosition:
    return AllocationActivePosition(
        strategy_id=strategy_id,
        symbol=symbol,
        direction=direction,
        opened_at=datetime(2026, 1, 1, 17, 0, tzinfo=timezone.utc),
    )


def _context(
    *,
    hour: int = 18,
    board_mode: str = "normal",
    kill_switch: str = "normal",
    open_positions: tuple[AllocationActivePosition, ...] = (),
) -> AllocationContext:
    return AllocationContext(
        now=datetime(2026, 1, 1, hour, 0, tzinfo=timezone.utc),
        board_mode=board_mode,
        kill_switch_state=kill_switch,
        regime_value=0.2,
        open_positions=open_positions,
    )


def _write_policy(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "allocation.yaml"
    path.write_text(
        "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def test_allocation_pass_through_keeps_all_candidates() -> None:
    policy = StrategyAllocationPolicy.pass_through()
    candidates = (
        _candidate(strategy_id="strat_a", score=1.0),
        _candidate(strategy_id="strat_b", score=0.8),
    )

    result = policy.allocate(candidates=candidates, context=_context())

    assert [item.strategy_id for item in result.selected] == ["strat_a", "strat_b"]
    assert all(outcome.selected for outcome in result.outcomes)
    assert {outcome.reason for outcome in result.outcomes} == {"pass_through"}


def test_allocation_tie_break_uses_priority_then_strategy_id(tmp_path: Path) -> None:
    config_path = _write_policy(
        tmp_path,
        {
            "profiles": {
                "active": {
                    "mode": "active",
                    "global": {
                        "require_strategy_config": True,
                        "hard_filters": {"session_utc_range": "00-23"},
                        "score": {"min_score": 0.0},
                    },
                    "tie_break": ["score_desc", "priority_asc", "strategy_id_asc"],
                    "strategies": {
                        "strat_a": {"enabled": True, "weight": 1.0},
                        "strat_b": {"enabled": True, "weight": 1.0},
                    },
                }
            }
        },
    )
    policy = StrategyAllocationPolicy.load(config_path, profile="active")
    result = policy.allocate(
        candidates=(
            _candidate(strategy_id="strat_b", score=1.0, priority=20),
            _candidate(strategy_id="strat_a", score=1.0, priority=10),
        ),
        context=_context(),
    )

    assert [item.strategy_id for item in result.selected] == ["strat_a"]
    rejected = [item for item in result.outcomes if not item.selected]
    assert len(rejected) == 1
    assert rejected[0].reason == "tie_break_lost"


def test_allocation_excludes_kill_switch_board_mode_spread_and_session(tmp_path: Path) -> None:
    config_path = _write_policy(
        tmp_path,
        {
            "profiles": {
                "active": {
                    "mode": "active",
                    "global": {
                        "require_strategy_config": True,
                        "hard_filters": {
                            "kill_switch_blocked_states": ["soft_stop", "hard_stop"],
                            "board_modes": ["normal"],
                            "spread_max": 0.003,
                            "session_utc_range": "16-21",
                        },
                        "score": {"min_score": 0.0},
                    },
                    "strategies": {"strat_a": {"enabled": True, "weight": 1.0}},
                }
            }
        },
    )
    policy = StrategyAllocationPolicy.load(config_path, profile="active")
    candidate = _candidate(strategy_id="strat_a", score=1.0, spread=0.005, slippage=0.001)

    blocked_kill_switch = policy.allocate(
        candidates=(candidate,),
        context=_context(kill_switch="soft_stop"),
    )
    assert blocked_kill_switch.selected == ()
    assert blocked_kill_switch.outcomes[0].reason == "kill_switch_blocked"

    blocked_board_mode = policy.allocate(
        candidates=(candidate,),
        context=_context(board_mode="guarded"),
    )
    assert blocked_board_mode.selected == ()
    assert blocked_board_mode.outcomes[0].reason == "board_mode_blocked"

    blocked_spread = policy.allocate(
        candidates=(candidate,),
        context=_context(),
    )
    assert blocked_spread.selected == ()
    assert blocked_spread.outcomes[0].reason == "spread_blocked"

    blocked_session = policy.allocate(
        candidates=(_candidate(strategy_id="strat_a", score=1.0, spread=0.001),),
        context=_context(hour=10),
    )
    assert blocked_session.selected == ()
    assert blocked_session.outcomes[0].reason == "session_blocked"


def test_allocation_applies_cost_penalty_and_score_floor(tmp_path: Path) -> None:
    config_path = _write_policy(
        tmp_path,
        {
            "profiles": {
                "active": {
                    "mode": "active",
                    "global": {
                        "require_strategy_config": True,
                        "hard_filters": {"session_utc_range": "00-23"},
                        "score": {"min_score": 0.5},
                        "cost_penalty": {"spread_weight": 100.0, "slippage_weight": 100.0},
                    },
                    "strategies": {
                        "strat_a": {"enabled": True, "weight": 1.0},
                        "strat_b": {"enabled": True, "weight": 1.0},
                    },
                }
            }
        },
    )
    policy = StrategyAllocationPolicy.load(config_path, profile="active")
    result = policy.allocate(
        candidates=(
            _candidate(strategy_id="strat_a", score=1.0, spread=0.0005, slippage=0.0005),
            _candidate(strategy_id="strat_b", score=1.0, spread=0.01, slippage=0.01),
        ),
        context=_context(),
    )

    assert [item.strategy_id for item in result.selected] == ["strat_a"]
    by_strategy = {item.strategy_id: item for item in result.outcomes}
    assert by_strategy["strat_b"].reason == "score_below_min"


def test_allocation_supports_n_strategy_expansion_by_config_only(tmp_path: Path) -> None:
    config_path = _write_policy(
        tmp_path,
        {
            "profiles": {
                "active": {
                    "mode": "active",
                    "global": {
                        "require_strategy_config": True,
                        "hard_filters": {"session_utc_range": "00-23"},
                        "score": {"min_score": 0.0},
                    },
                    "strategies": {
                        "strat_a": {"enabled": True, "weight": 1.0},
                        "strat_b": {"enabled": True, "weight": 1.0},
                        "strat_c": {"enabled": True, "weight": 1.5},
                    },
                }
            }
        },
    )
    policy = StrategyAllocationPolicy.load(config_path, profile="active")
    result = policy.allocate(
        candidates=(
            _candidate(strategy_id="strat_a", score=1.0),
            _candidate(strategy_id="strat_b", score=1.0),
            _candidate(strategy_id="strat_c", score=1.0),
        ),
        context=_context(),
    )

    assert [item.strategy_id for item in result.selected] == ["strat_c"]


def test_allocation_select_many_keeps_all_accepted_candidates(tmp_path: Path) -> None:
    config_path = _write_policy(
        tmp_path,
        {
            "profiles": {
                "active": {
                    "mode": "active",
                    "global": {
                        "require_strategy_config": True,
                        "selection": {"mode": "select_many"},
                        "hard_filters": {"session_utc_range": "00-23"},
                        "score": {"min_score": 0.0},
                    },
                    "tie_break": ["score_desc", "priority_asc", "strategy_id_asc"],
                    "strategies": {
                        "strat_a": {"enabled": True, "weight": 1.0},
                        "strat_b": {"enabled": True, "weight": 1.0},
                    },
                }
            }
        },
    )
    policy = StrategyAllocationPolicy.load(config_path, profile="active")
    result = policy.allocate(
        candidates=(
            _candidate(strategy_id="strat_a", score=1.0, priority=10),
            _candidate(strategy_id="strat_b", score=1.1, priority=20),
        ),
        context=_context(),
    )

    assert {item.strategy_id for item in result.selected} == {"strat_a", "strat_b"}
    assert all(outcome.selected for outcome in result.outcomes)


def test_allocation_select_many_honors_max_per_symbol(tmp_path: Path) -> None:
    config_path = _write_policy(
        tmp_path,
        {
            "profiles": {
                "active": {
                    "mode": "active",
                    "global": {
                        "require_strategy_config": True,
                        "selection": {"mode": "select_many", "max_per_symbol": 2},
                        "hard_filters": {"session_utc_range": "00-23"},
                        "score": {"min_score": 0.0},
                    },
                    "tie_break": ["score_desc", "priority_asc", "strategy_id_asc"],
                    "strategies": {
                        "strat_a": {"enabled": True, "weight": 1.0},
                        "strat_b": {"enabled": True, "weight": 1.0},
                        "strat_c": {"enabled": True, "weight": 1.0},
                    },
                }
            }
        },
    )
    policy = StrategyAllocationPolicy.load(config_path, profile="active")
    result = policy.allocate(
        candidates=(
            _candidate(strategy_id="strat_a", score=1.3, priority=30),
            _candidate(strategy_id="strat_b", score=1.2, priority=20),
            _candidate(strategy_id="strat_c", score=1.1, priority=10),
        ),
        context=_context(),
    )

    assert [item.strategy_id for item in result.selected] == ["strat_a", "strat_b"]
    by_id = {outcome.strategy_id: outcome for outcome in result.outcomes}
    assert by_id["strat_c"].selected is False
    assert by_id["strat_c"].reason == "selection_limit"


def test_allocation_select_many_handles_duplicate_strategy_ids(tmp_path: Path) -> None:
    config_path = _write_policy(
        tmp_path,
        {
            "profiles": {
                "active": {
                    "mode": "active",
                    "global": {
                        "require_strategy_config": True,
                        "selection": {"mode": "select_many", "max_per_symbol": 1},
                        "hard_filters": {"session_utc_range": "00-23"},
                        "score": {"min_score": 0.0},
                    },
                    "tie_break": ["score_desc", "priority_asc", "strategy_id_asc"],
                    "strategies": {
                        "strat_a": {"enabled": True, "weight": 1.0},
                    },
                }
            }
        },
    )
    policy = StrategyAllocationPolicy.load(config_path, profile="active")
    result = policy.allocate(
        candidates=(
            _candidate(strategy_id="strat_a", score=1.2, priority=20),
            _candidate(strategy_id="strat_a", score=1.1, priority=10),
        ),
        context=_context(),
    )

    assert len(result.selected) == 1
    selected = [outcome for outcome in result.outcomes if outcome.selected]
    rejected = [outcome for outcome in result.outcomes if not outcome.selected]
    assert len(selected) == 1
    assert len(rejected) == 1
    assert rejected[0].reason == "selection_limit"


def test_allocation_blocks_candidate_when_same_portfolio_group_is_open(tmp_path: Path) -> None:
    config_path = _write_policy(
        tmp_path,
        {
            "profiles": {
                "active": {
                    "mode": "active",
                    "global": {
                        "require_strategy_config": True,
                        "hard_filters": {"session_utc_range": "00-23"},
                        "score": {"min_score": 0.0},
                    },
                    "strategies": {
                        "open_strat": {
                            "enabled": True,
                            "weight": 1.0,
                            "portfolio": {"group": "trend_breakout"},
                        },
                        "strat_a": {
                            "enabled": True,
                            "weight": 1.0,
                            "portfolio": {
                                "group": "trend_breakout",
                                "active_group_policy": "block",
                            },
                        },
                    },
                }
            }
        },
    )
    policy = StrategyAllocationPolicy.load(config_path, profile="active")
    result = policy.allocate(
        candidates=(_candidate(strategy_id="strat_a", score=1.1),),
        context=_context(open_positions=(_position(),)),
    )

    assert result.selected == ()
    assert result.outcomes[0].reason == "active_group_conflict"


def test_allocation_penalizes_long_expected_holding_minutes(tmp_path: Path) -> None:
    config_path = _write_policy(
        tmp_path,
        {
            "profiles": {
                "active": {
                    "mode": "active",
                    "global": {
                        "require_strategy_config": True,
                        "hard_filters": {"session_utc_range": "00-23"},
                        "score": {"min_score": 0.0},
                        "portfolio": {"holding_minute_weight": 0.001},
                    },
                    "tie_break": ["score_desc", "role_priority_asc", "priority_asc", "strategy_id_asc"],
                    "strategies": {
                        "fast": {
                            "enabled": True,
                            "weight": 1.0,
                            "portfolio": {"expected_holding_minutes": 45, "role_priority": 10},
                        },
                        "slow": {
                            "enabled": True,
                            "weight": 1.0,
                            "portfolio": {"expected_holding_minutes": 240, "role_priority": 20},
                        },
                    },
                }
            }
        },
    )
    policy = StrategyAllocationPolicy.load(config_path, profile="active")
    result = policy.allocate(
        candidates=(
            _candidate(strategy_id="fast", score=1.0),
            _candidate(strategy_id="slow", score=1.0),
        ),
        context=_context(),
    )

    assert [item.strategy_id for item in result.selected] == ["fast"]
    by_id = {outcome.strategy_id: outcome for outcome in result.outcomes}
    assert by_id["slow"].selected is False
    assert by_id["slow"].reason == "tie_break_lost"


def test_allocation_blocks_same_symbol_when_configured(tmp_path: Path) -> None:
    config_path = _write_policy(
        tmp_path,
        {
            "profiles": {
                "active": {
                    "mode": "active",
                    "global": {
                        "require_strategy_config": True,
                        "hard_filters": {"session_utc_range": "00-23"},
                        "score": {"min_score": 0.0},
                    },
                    "strategies": {
                        "strat_a": {
                            "enabled": True,
                            "weight": 1.0,
                            "portfolio": {"active_symbol_policy": "block"},
                        },
                    },
                }
            }
        },
    )
    policy = StrategyAllocationPolicy.load(config_path, profile="active")
    result = policy.allocate(
        candidates=(_candidate(strategy_id="strat_a", score=1.0),),
        context=_context(open_positions=(_position(strategy_id="other_group", symbol="USDJPY"),)),
    )

    assert result.selected == ()
    assert result.outcomes[0].reason == "active_symbol_conflict"


def test_allocation_defers_same_portfolio_group_when_configured(tmp_path: Path) -> None:
    config_path = _write_policy(
        tmp_path,
        {
            "profiles": {
                "active": {
                    "mode": "active",
                    "global": {
                        "require_strategy_config": True,
                        "hard_filters": {"session_utc_range": "00-23"},
                        "score": {"min_score": 0.0},
                    },
                    "strategies": {
                        "open_strat": {
                            "enabled": True,
                            "weight": 1.0,
                            "portfolio": {"group": "trend_breakout"},
                        },
                        "strat_a": {
                            "enabled": True,
                            "weight": 1.0,
                            "portfolio": {
                                "group": "trend_breakout",
                                "active_group_policy": "defer",
                            },
                        },
                    },
                }
            }
        },
    )
    policy = StrategyAllocationPolicy.load(config_path, profile="active")
    result = policy.allocate(
        candidates=(_candidate(strategy_id="strat_a", score=1.1),),
        context=_context(open_positions=(_position(),)),
    )

    assert result.selected == ()
    assert result.outcomes[0].reason == "active_group_deferred"


def test_allocation_blocks_same_exposure_bucket_when_configured(tmp_path: Path) -> None:
    config_path = _write_policy(
        tmp_path,
        {
            "profiles": {
                "active": {
                    "mode": "active",
                    "global": {
                        "require_strategy_config": True,
                        "hard_filters": {"session_utc_range": "00-23"},
                        "score": {"min_score": 0.0},
                    },
                    "strategies": {
                        "open_strat": {
                            "enabled": True,
                            "weight": 1.0,
                            "portfolio": {"exposure_bucket": "usd_jpy_breakout_long"},
                        },
                        "strat_a": {
                            "enabled": True,
                            "weight": 1.0,
                            "portfolio": {
                                "exposure_bucket": "usd_jpy_breakout_long",
                                "active_exposure_policy": "block",
                            },
                        },
                    },
                }
            }
        },
    )
    policy = StrategyAllocationPolicy.load(config_path, profile="active")
    result = policy.allocate(
        candidates=(_candidate(strategy_id="strat_a", score=1.0),),
        context=_context(open_positions=(_position(),)),
    )

    assert result.selected == ()
    assert result.outcomes[0].reason == "active_exposure_conflict"


def test_allocation_blocks_when_group_limit_reached(tmp_path: Path) -> None:
    config_path = _write_policy(
        tmp_path,
        {
            "profiles": {
                "active": {
                    "mode": "active",
                    "global": {
                        "require_strategy_config": True,
                        "hard_filters": {"session_utc_range": "00-23"},
                        "score": {"min_score": 0.0},
                    },
                    "strategies": {
                        "open_strat": {
                            "enabled": True,
                            "weight": 1.0,
                            "portfolio": {"group": "trend_breakout"},
                        },
                        "strat_a": {
                            "enabled": True,
                            "weight": 1.0,
                            "portfolio": {
                                "group": "trend_breakout",
                                "max_active_per_group": 1,
                            },
                        },
                    },
                }
            }
        },
    )
    policy = StrategyAllocationPolicy.load(config_path, profile="active")
    result = policy.allocate(
        candidates=(_candidate(strategy_id="strat_a", score=1.0),),
        context=_context(open_positions=(_position(),)),
    )

    assert result.selected == ()
    assert result.outcomes[0].reason == "active_group_limit"


def test_allocation_penalizes_slot_cost(tmp_path: Path) -> None:
    config_path = _write_policy(
        tmp_path,
        {
            "profiles": {
                "active": {
                    "mode": "active",
                    "global": {
                        "require_strategy_config": True,
                        "hard_filters": {"session_utc_range": "00-23"},
                        "score": {"min_score": 0.0},
                    },
                    "tie_break": ["score_desc", "role_priority_asc", "priority_asc", "strategy_id_asc"],
                    "strategies": {
                        "cheap_slot": {
                            "enabled": True,
                            "weight": 1.0,
                            "portfolio": {"slot_cost": 0.01, "role_priority": 10},
                        },
                        "expensive_slot": {
                            "enabled": True,
                            "weight": 1.0,
                            "portfolio": {"slot_cost": 0.20, "role_priority": 20},
                        },
                    },
                }
            }
        },
    )
    policy = StrategyAllocationPolicy.load(config_path, profile="active")
    result = policy.allocate(
        candidates=(
            _candidate(strategy_id="cheap_slot", score=1.0),
            _candidate(strategy_id="expensive_slot", score=1.0),
        ),
        context=_context(),
    )

    assert [item.strategy_id for item in result.selected] == ["cheap_slot"]
    by_id = {outcome.strategy_id: outcome for outcome in result.outcomes}
    assert by_id["expensive_slot"].selected is False
    assert by_id["expensive_slot"].reason == "tie_break_lost"
