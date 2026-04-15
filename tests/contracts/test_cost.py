"""CI gate I3 — Cost positivity.

See ``docs/invariants.md`` §I3 and ``docs/architecture.md`` §2.

For every non-zero configuration of ``config/execution.yaml`` (spread,
slippage, commission, swap, weekend gap), a round-trip trade must produce
``realized_cost > 0``. A zero-cost round trip is a bug — the bar at which
cost must be modelled honestly is the bar at which any backtest number is
meaningful.

These assertions exercise :func:`src.execution.cost.round_trip_cost`
against the committed ``config/execution.yaml`` with representative
symbol / side / session / holding combinations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.execution.cost import (
    CostConfigError,
    ExecutionCostConfig,
    load_execution_cost_config,
    round_trip_cost,
    session_for_timestamp,
)

EXECUTION_YAML = Path("config") / "execution.yaml"


@pytest.fixture(scope="module")
def cost_config() -> ExecutionCostConfig:
    return load_execution_cost_config(EXECUTION_YAML)


# ---------------------------------------------------------------------------
# Baseline round-trip positivity
# ---------------------------------------------------------------------------


def _london_ts() -> datetime:
    # Wednesday 10:00 UTC → squarely inside the london session, no rollover.
    return datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)


def test_spread_non_zero_yields_positive_cost(cost_config: ExecutionCostConfig) -> None:
    result = round_trip_cost(
        config=cost_config,
        symbol="USDJPY",
        side="long",
        timestamp=_london_ts(),
        expected_holding_minutes=30,
    )
    assert result.spread > 0, "spread must be positive for london USDJPY"


def test_slippage_non_zero_yields_positive_cost(cost_config: ExecutionCostConfig) -> None:
    result = round_trip_cost(
        config=cost_config,
        symbol="USDJPY",
        side="long",
        timestamp=_london_ts(),
        expected_holding_minutes=30,
    )
    assert result.slippage > 0, "base-session slippage p50 must be positive"


def test_commission_non_zero_yields_positive_cost(cost_config: ExecutionCostConfig) -> None:
    result = round_trip_cost(
        config=cost_config,
        symbol="USDJPY",
        side="long",
        timestamp=_london_ts(),
        expected_holding_minutes=30,
    )
    assert result.commission > 0, "USDJPY per-side commission must be positive"


def test_swap_non_zero_yields_positive_cost(cost_config: ExecutionCostConfig) -> None:
    # USDJPY `long_per_night` is negative (pay) in the committed config, so a
    # holding window that crosses 21:00 UTC charges swap.
    opened = datetime(2026, 4, 15, 20, 0, tzinfo=timezone.utc)  # Wed 20:00 UTC
    result = round_trip_cost(
        config=cost_config,
        symbol="USDJPY",
        side="long",
        timestamp=opened,
        expected_holding_minutes=120,  # crosses 21:00 UTC rollover
    )
    assert result.swap > 0, "long USDJPY across rollover must charge swap"


def test_weekend_gap_non_zero_yields_positive_cost(cost_config: ExecutionCostConfig) -> None:
    # Friday 20:00 UTC → crosses Friday 21:00 UTC weekend close.
    opened = datetime(2026, 4, 17, 20, 0, tzinfo=timezone.utc)  # Friday
    result = round_trip_cost(
        config=cost_config,
        symbol="USDJPY",
        side="long",
        timestamp=opened,
        expected_holding_minutes=60 * 72,  # hold through the weekend
    )
    assert result.weekend_gap > 0, "holding through Friday 21:00 UTC must charge weekend gap"


def test_total_round_trip_cost_positive_in_london(
    cost_config: ExecutionCostConfig,
) -> None:
    result = round_trip_cost(
        config=cost_config,
        symbol="USDJPY",
        side="long",
        timestamp=_london_ts(),
        expected_holding_minutes=30,
    )
    assert result.total > 0, "london intraday round trip must cost > 0"


# ---------------------------------------------------------------------------
# Sweep: no zero-cost paths across sessions / sides
# ---------------------------------------------------------------------------


SESSIONS_WITH_TS: list[tuple[str, datetime]] = [
    ("asia", datetime(2026, 4, 15, 3, 0, tzinfo=timezone.utc)),
    ("london", datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)),
    ("overlap", datetime(2026, 4, 15, 14, 0, tzinfo=timezone.utc)),
    ("ny", datetime(2026, 4, 15, 18, 0, tzinfo=timezone.utc)),
    ("off_hours", datetime(2026, 4, 15, 22, 0, tzinfo=timezone.utc)),
]


@pytest.mark.parametrize("label,ts", SESSIONS_WITH_TS)
@pytest.mark.parametrize("side", ["long", "short"])
def test_no_zero_cost_path_any_session_any_side(
    cost_config: ExecutionCostConfig, label: str, ts: datetime, side: str,
) -> None:
    """Every (session, side) combination must yield positive round-trip cost.

    If any branch of ``config/execution.yaml`` collapses round-trip cost
    to zero, the invariant is broken structurally — callers may still
    report PF > 1 artifacts.
    """

    result = round_trip_cost(
        config=cost_config,
        symbol="USDJPY",
        side=side,  # type: ignore[arg-type]
        timestamp=ts,
        expected_holding_minutes=30,
    )
    assert result.total > 0, f"zero cost for session={label}, side={side}"


# ---------------------------------------------------------------------------
# Session boundary detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hour,expected",
    [
        (0, "asia"),
        (5, "asia"),
        (6, "london"),
        (11, "london"),
        (12, "overlap"),
        (15, "overlap"),
        (16, "ny"),
        (20, "ny"),
        (21, "off_hours"),
        (23, "off_hours"),
    ],
)
def test_session_detection_weekday(hour: int, expected: str) -> None:
    ts = datetime(2026, 4, 15, hour, 0, tzinfo=timezone.utc)  # Wednesday
    assert session_for_timestamp(ts) == expected


def test_saturday_is_off_hours() -> None:
    ts = datetime(2026, 4, 18, 10, 0, tzinfo=timezone.utc)  # Saturday mid-day
    assert session_for_timestamp(ts) == "off_hours"


def test_friday_after_close_is_off_hours() -> None:
    ts = datetime(2026, 4, 17, 22, 0, tzinfo=timezone.utc)  # Friday post-21:00
    assert session_for_timestamp(ts) == "off_hours"


def test_naive_timestamp_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        session_for_timestamp(datetime(2026, 4, 15, 10, 0))


# ---------------------------------------------------------------------------
# Config loader failure modes
# ---------------------------------------------------------------------------


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(CostConfigError, match="missing"):
        load_execution_cost_config(tmp_path / "does_not_exist.yaml")


def test_malformed_config_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("spread: []\nslippage: []\ncommission: []\n", encoding="utf-8")
    # Missing 'swap' and 'weekend_gap' sections.
    with pytest.raises(CostConfigError, match="missing required sections"):
        load_execution_cost_config(bad)


def test_unknown_symbol_falls_back_to_default(
    cost_config: ExecutionCostConfig,
) -> None:
    # `GBPJPY` is not keyed in the committed config — must reach the `default`
    # bucket rather than raise.
    result = round_trip_cost(
        config=cost_config,
        symbol="GBPJPY",
        side="long",
        timestamp=_london_ts(),
        expected_holding_minutes=30,
    )
    assert result.total > 0


# ---------------------------------------------------------------------------
# Holding-window dependencies
# ---------------------------------------------------------------------------


def test_short_intraday_charges_no_swap(cost_config: ExecutionCostConfig) -> None:
    # Open 09:00 UTC, hold 60 minutes → no rollover crossing.
    result = round_trip_cost(
        config=cost_config,
        symbol="USDJPY",
        side="long",
        timestamp=datetime(2026, 4, 15, 9, 0, tzinfo=timezone.utc),
        expected_holding_minutes=60,
    )
    assert result.swap == 0.0


def test_multi_night_accrues_multiple_swap_charges(
    cost_config: ExecutionCostConfig,
) -> None:
    # Open Monday 10:00 UTC, hold 3 days. Crosses 3 rollovers (Mon/Tue/Wed 21:00).
    opened = datetime(2026, 4, 13, 10, 0, tzinfo=timezone.utc)  # Monday
    single_night = round_trip_cost(
        config=cost_config,
        symbol="USDJPY",
        side="long",
        timestamp=opened,
        expected_holding_minutes=60 * 12,  # 10:00 -> 22:00 same day, 1 rollover
    )
    three_nights = round_trip_cost(
        config=cost_config,
        symbol="USDJPY",
        side="long",
        timestamp=opened,
        expected_holding_minutes=60 * 60,  # 60h → 3 rollovers
    )
    assert three_nights.swap > single_night.swap > 0.0


def test_short_side_receive_does_not_discount(
    cost_config: ExecutionCostConfig,
) -> None:
    # USDJPY `short_per_night` is positive (receive) in the committed config.
    # I3 requires round-trip cost to stay positive — receives must not
    # discount the other components.
    opened = datetime(2026, 4, 15, 20, 0, tzinfo=timezone.utc)  # cross 21 UTC
    result = round_trip_cost(
        config=cost_config,
        symbol="USDJPY",
        side="short",
        timestamp=opened,
        expected_holding_minutes=120,
    )
    assert result.swap == 0.0  # receive modelled as zero cost, not credit
    assert result.total > 0
