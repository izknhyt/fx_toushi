"""Realistic round-trip cost model — the entry point for CI gate I3.

Reads ``config/execution.yaml`` and returns a :class:`RoundTripCost` for a
given symbol / side / session / timestamp / holding window. Every strategy
that computes ``Candidate.estimated_cost`` pulls its number from this
module; constants and ad-hoc values are forbidden (enforced by reviews and
the contract-guard agent).

The prior ``src/backtest/paper_poc.py`` hardcoded spread/slippage/commission
defaults at zero; this module replaces that with a config-driven, realistic
model that charges spread × 2 (entry + exit), slippage × 2 (sampled by
session × liquidity state), per-side commission × 2, swap per rollover
crossed, and a weekend-gap premium for positions held through Friday
close.

Invariant I3 (``docs/invariants.md``): every non-zero configuration must
produce ``realized_cost > 0`` for a round-trip. This module makes that
invariant structural — zero cost is unreachable when any of the five
sections in ``config/execution.yaml`` is populated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

__all__ = [
    "CostConfigError",
    "ExecutionCostConfig",
    "RoundTripCost",
    "load_execution_cost_config",
    "round_trip_cost",
]


DEFAULT_EXECUTION_YAML = Path("config") / "execution.yaml"

Side = Literal["long", "short"]
Session = Literal["asia", "london", "overlap", "ny", "off_hours"]

# Rollover convention. 21:00 UTC is common across retail brokers for daily
# interest accrual. Friday 21:00 UTC marks the weekend close.
ROLLOVER_HOUR_UTC: int = 21

# Session mapping (UTC hour ranges, half-open [start, end)).
#
# Boundaries chosen conservatively to match retail FX data conventions:
# Tokyo opens ~00:00 UTC, London ~07:00-08:00, New York ~12:00-13:00,
# close ~21:00. Specific windows have real spread/liquidity signatures
# reflected in ``config/execution.yaml``.
_SESSION_WINDOWS: tuple[tuple[int, int, Session], ...] = (
    (0, 6, "asia"),
    (6, 12, "london"),
    (12, 16, "overlap"),
    (16, 21, "ny"),
    (21, 24, "off_hours"),
)


class CostConfigError(RuntimeError):
    """Raised when ``config/execution.yaml`` is missing required fields."""


@dataclass(frozen=True, slots=True)
class ExecutionCostConfig:
    """Parsed view of ``config/execution.yaml``.

    Kept opaque on purpose — callers go through :func:`round_trip_cost` and
    receive a :class:`RoundTripCost`. Direct field access is reserved for
    admission / backtest wiring that needs to explain *why* a number came
    out the way it did (e.g. which bucket of the spread curve applied).
    """

    raw: dict


@dataclass(frozen=True, slots=True)
class RoundTripCost:
    """Aggregated cost of opening and closing a single position.

    All numbers are in **price units** (not pips, not bps) so they compose
    directly with :class:`src.contract.Candidate`'s ``entry`` / ``stop`` /
    ``target``.

    All five components are ``>= 0`` by construction. Swap *receives* (when
    a holding direction accrues positive interest) are modelled as zero
    cost rather than a credit — a deliberate pessimistic choice that keeps
    CI gate I3 structural.
    """

    spread: float
    slippage: float
    commission: float
    swap: float
    weekend_gap: float

    @property
    def total(self) -> float:
        return (
            self.spread
            + self.slippage
            + self.commission
            + self.swap
            + self.weekend_gap
        )


def load_execution_cost_config(
    path: Path = DEFAULT_EXECUTION_YAML,
) -> ExecutionCostConfig:
    """Load and validate ``config/execution.yaml``.

    Raises :class:`CostConfigError` when the file is missing, unparseable,
    or does not contain the minimum schema (``spread``, ``slippage``,
    ``commission``, ``swap``, ``weekend_gap`` sections).
    """

    if not path.exists():
        raise CostConfigError(f"execution config missing at {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CostConfigError(f"execution config parse error: {exc}") from exc
    if not isinstance(data, dict):
        raise CostConfigError("execution config must be a mapping at the top level")

    required = {"spread", "slippage", "commission", "swap", "weekend_gap"}
    missing = required - data.keys()
    if missing:
        raise CostConfigError(
            "execution config missing required sections: "
            + ", ".join(sorted(missing))
        )

    return ExecutionCostConfig(raw=data)


# ---------------------------------------------------------------------------
# Session / timing helpers
# ---------------------------------------------------------------------------


def session_for_timestamp(timestamp: datetime) -> Session:
    """Map a UTC timestamp to one of the five session buckets.

    Naive timestamps raise :class:`ValueError` — strategies must carry
    tz-aware timestamps per :class:`src.contract.Candidate`.
    """

    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    utc = timestamp.astimezone(timezone.utc)
    hour = utc.hour

    # Weekends: FX retail venues close Friday 21:00 UTC through Sunday
    # 21:00 UTC. Strategies should not emit candidates into that window;
    # if they do, we treat the bar as ``off_hours`` so the cost model
    # stays consistent.
    weekday = utc.weekday()  # Monday = 0 ... Sunday = 6
    if weekday == 5:
        return "off_hours"
    if weekday == 6 and hour < ROLLOVER_HOUR_UTC:
        return "off_hours"
    if weekday == 4 and hour >= ROLLOVER_HOUR_UTC:
        return "off_hours"

    for start_h, end_h, label in _SESSION_WINDOWS:
        if start_h <= hour < end_h:
            return label
    return "off_hours"  # safety net, unreachable given the windows above


def _count_rollover_crossings(start: datetime, holding_minutes: int) -> int:
    """Count ``ROLLOVER_HOUR_UTC`` crossings inside ``[start, end)``.

    Used to price nightly swap. A holding window that opens before 21:00
    UTC and closes after 21:00 UTC on the same day counts as 1 crossing.
    Multi-day holdings accrue one crossing per calendar day they cover.
    """

    if holding_minutes <= 0:
        return 0
    start_utc = start.astimezone(timezone.utc)
    end_utc = start_utc + timedelta(minutes=holding_minutes)

    # First candidate rollover: today at 21:00 UTC if still ahead,
    # otherwise tomorrow at 21:00 UTC.
    today_rollover = start_utc.replace(
        hour=ROLLOVER_HOUR_UTC, minute=0, second=0, microsecond=0
    )
    candidate = today_rollover if today_rollover > start_utc else today_rollover + timedelta(days=1)

    count = 0
    while candidate < end_utc:
        count += 1
        candidate += timedelta(days=1)
    return count


def _count_weekend_crossings(start: datetime, holding_minutes: int) -> int:
    """Count Friday-21:00-UTC crossings inside ``[start, end)``.

    A holding window that opens before Friday 21:00 UTC and closes after
    Sunday open is counted as one weekend. Multi-week holdings pick up one
    weekend each.
    """

    if holding_minutes <= 0:
        return 0
    start_utc = start.astimezone(timezone.utc)
    end_utc = start_utc + timedelta(minutes=holding_minutes)

    # Walk calendar days inside the window and check for Friday 21:00 UTC.
    count = 0
    cursor = start_utc.replace(hour=ROLLOVER_HOUR_UTC, minute=0, second=0, microsecond=0)
    # Step back to the latest Friday 21:00 <= start_utc (or earlier).
    while cursor > start_utc:
        cursor -= timedelta(days=1)
    # Now walk forward, counting Friday 21:00 UTC instants strictly between
    # start_utc (exclusive) and end_utc (exclusive).
    while cursor < end_utc:
        cursor += timedelta(days=1)
        if cursor <= start_utc:
            continue
        if cursor.weekday() == 4:  # Friday
            count += 1
    return count


# ---------------------------------------------------------------------------
# Config lookup helpers
# ---------------------------------------------------------------------------


def _symbol_bucket(table: dict, symbol: str) -> dict:
    """Look up ``table[symbol]`` falling back to ``table["default"]``.

    Raises :class:`CostConfigError` when neither is present.
    """

    if symbol in table:
        return dict(table[symbol])
    if "default" in table:
        return dict(table["default"])
    raise CostConfigError(f"no cost bucket for symbol={symbol!r} and no default")


def _require_float(container: dict, key: str, context: str) -> float:
    if key not in container:
        raise CostConfigError(f"execution config missing {context}.{key}")
    value = container[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise CostConfigError(f"execution config {context}.{key} must be numeric")
    return float(value)


# ---------------------------------------------------------------------------
# Public cost computation
# ---------------------------------------------------------------------------


def round_trip_cost(
    *,
    config: ExecutionCostConfig,
    symbol: str,
    side: Side,
    timestamp: datetime,
    expected_holding_minutes: int,
    volatile: bool | None = None,
) -> RoundTripCost:
    """Compute realistic round-trip cost for a candidate.

    ``volatile`` forces the slippage distribution to the "volatile" branch
    (news, illiquid). If unset, the module infers volatility from the
    session: ``off_hours`` is treated as volatile, everything else as base.

    Round-trip charges:
        * spread × 2 (entry + exit).
        * slippage × 2 (p50 draw per side; callers that want tail risk
          should recompute with the p90 table themselves).
        * commission × 2 (per-side charge each leg).
        * swap per rollover crossing, charging ``|per_night|`` only when
          the config value is negative (i.e. a net pay). Positive swap
          (receive) is modelled as zero cost, not a credit.
        * weekend gap × weekends crossed.

    No receive-side credit is ever returned — ``RoundTripCost`` is strictly
    non-negative across all components, so CI gate I3 holds structurally.
    """

    if side not in ("long", "short"):
        raise ValueError(f"side must be 'long' or 'short', got {side!r}")
    if expected_holding_minutes < 0:
        raise ValueError("expected_holding_minutes must be non-negative")
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")

    raw = config.raw
    session = session_for_timestamp(timestamp)

    # --- spread ---
    spread_symbol = _symbol_bucket(raw["spread"], symbol)
    spread_per_side = _require_float(spread_symbol, session, f"spread.{symbol}")
    spread_cost = spread_per_side * 2.0

    # --- slippage ---
    slippage_symbol = _symbol_bucket(raw["slippage"], symbol)
    if volatile is None:
        volatile = session == "off_hours"
    mode_key = "volatile" if volatile else "base"
    if mode_key not in slippage_symbol:
        raise CostConfigError(
            f"execution config slippage.{symbol} missing mode {mode_key!r}"
        )
    slippage_bucket = slippage_symbol[mode_key]
    if not isinstance(slippage_bucket, dict):
        raise CostConfigError(
            f"execution config slippage.{symbol}.{mode_key} must be a mapping"
        )
    slippage_p50 = _require_float(slippage_bucket, "p50", f"slippage.{symbol}.{mode_key}")
    slippage_cost = slippage_p50 * 2.0

    # --- commission ---
    commission_symbol = _symbol_bucket(raw["commission"], symbol)
    commission_per_side = _require_float(commission_symbol, "per_side", f"commission.{symbol}")
    commission_cost = commission_per_side * 2.0

    # --- swap ---
    swap_cost = 0.0
    rollover_crossings = _count_rollover_crossings(timestamp, expected_holding_minutes)
    if rollover_crossings > 0:
        swap_symbol = _symbol_bucket(raw["swap"], symbol)
        per_night_key = f"{side}_per_night"
        per_night_value = _require_float(swap_symbol, per_night_key, f"swap.{symbol}")
        # Negative config value = we pay; positive = we receive.
        # Charge only the pay side so `RoundTripCost.total` stays >= 0.
        swap_cost = max(0.0, -per_night_value) * rollover_crossings

    # --- weekend gap ---
    weekend_gap_cost = 0.0
    weekend_crossings = _count_weekend_crossings(timestamp, expected_holding_minutes)
    if weekend_crossings > 0:
        weekend_symbol = _symbol_bucket(raw["weekend_gap"], symbol)
        weekend_premium = _require_float(weekend_symbol, "premium", f"weekend_gap.{symbol}")
        weekend_gap_cost = weekend_premium * weekend_crossings

    return RoundTripCost(
        spread=spread_cost,
        slippage=slippage_cost,
        commission=commission_cost,
        swap=swap_cost,
        weekend_gap=weekend_gap_cost,
    )
