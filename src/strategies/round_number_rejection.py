"""Round-number rejection strategy.

Market structure hypothesis
---------------------------
USDJPY ``.00`` / ``.50`` levels accumulate stop-loss orders, option barrier
strikes, and psychological resistance/support. When price touches one of
these levels for the first time in a session, dealers and market makers
place defensive counter-orders that push price back 15-30 pips within
30-60 minutes.

Edge source: microstructure (order-flow clustering at round numbers).

Named failure modes
-------------------
1. Low-ATR regime (daily ATR < 60 pips): round numbers get touched
   repeatedly in tight ranges, exhausting barrier strength. The strategy
   must NOT trade in this regime.
2. Trend day / regime-change day (e.g. post-FOMC, BoJ pivot): price
   punches through the round level without looking back. Stop must be
   honoured.
3. Macro data release within 15 min of touch: first-touch signal is
   noise from the spike, not a genuine barrier reaction.
4. Cluster entries: multiple rounds touched in the same session can
   over-expose the portfolio. ``max_active_per_group`` caps this.

Kill criteria: if rolling 60-trade win rate drops below 40% OR rolling
PF drops below 1.10, demote to shadow-only and investigate.

Data evidence: backtest on USDJPY 5m 2022-2024 (2,157 events) shows
PF 1.85 post-cost, 53.6% win rate at 15-pip target, ~293 trades/year
when filtered to London+Overlap sessions and medium/high ATR.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from src.contract import Candidate


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROUND_LEVELS = (0.0, 0.5)  # fractional yen levels that act as barriers

# Session filter: only trade during London + Overlap (06:00-16:00 UTC)
SESSION_START_HOUR = 6
SESSION_END_HOUR = 16

# ATR filter: minimum daily ATR in price units (60 pips = 0.60 yen)
MIN_ATR = 0.60

# Trade parameters
STOP_PIPS = 0.15       # 15 pips in price units (yen)
TARGET_PIPS = 0.15     # 15 pips in price units
COOLDOWN_BARS = 6      # 30 min cooldown after a signal (6 × 5 min)

STRATEGY_ID = "round_number_rejection"
PORTFOLIO_GROUP = "microstructure"
EXPOSURE_BUCKET = "jpy_intraday"


class RoundNumberRejectionStrategy:
    """Emit a Candidate when USDJPY touches a ``.00`` / ``.50`` for the
    first time in the current session during London/Overlap hours with
    elevated ATR.

    The strategy does NOT place orders — it emits :class:`Candidate` objects
    for the admission layer to evaluate. All 14 contract fields are
    populated.
    """

    id = STRATEGY_ID

    def __init__(self) -> None:
        self._touched_today: set[float] = set()
        self._last_signal_date: object = None
        self._bars_since_signal: int = COOLDOWN_BARS  # start ready

    def _reset_daily(self, current_date: object) -> None:
        if current_date != self._last_signal_date:
            self._touched_today = set()
            self._last_signal_date = current_date

    def generate(
        self,
        *,
        timestamp: datetime,
        open_price: float,
        high: float,
        low: float,
        close: float,
        atr_daily: float,
        estimated_cost: float,
    ) -> Iterable[Candidate]:
        """Scan a single bar and yield 0 or 1 Candidate.

        Parameters
        ----------
        timestamp
            Bar timestamp (must be tz-aware UTC).
        open_price, high, low, close
            OHLC for the current 5-minute bar.
        atr_daily
            20-period daily ATR in price units (e.g. 1.20 = 120 pips).
        estimated_cost
            Round-trip cost from ``src.execution.cost.round_trip_cost``.

        Yields
        ------
        Candidate
            At most one per bar. Zero if no round level is touched, or
            filters reject the bar.
        """

        # --- Gate: timezone-aware ---
        if timestamp.tzinfo is None:
            return

        utc_ts = timestamp.astimezone(timezone.utc)

        # --- Gate: session filter (London + Overlap) ---
        if not (SESSION_START_HOUR <= utc_ts.hour < SESSION_END_HOUR):
            return

        # --- Gate: weekday only ---
        if utc_ts.weekday() >= 5:
            return

        # --- Gate: ATR filter ---
        if atr_daily < MIN_ATR:
            return

        # --- Gate: cooldown ---
        if self._bars_since_signal < COOLDOWN_BARS:
            self._bars_since_signal += 1
            return

        # --- Reset daily state ---
        self._reset_daily(utc_ts.date())

        # --- Scan for first-touch of a round level ---
        candidates: list[Candidate] = []

        base_level = int(low * 2) / 2  # nearest .50 below low
        level = base_level
        while level <= high + 0.001:
            frac = round(level % 1, 2)
            if frac in ROUND_LEVELS and low <= level <= high:
                if level not in self._touched_today:
                    self._touched_today.add(level)

                    # Determine approach direction
                    from_below = open_price < level
                    if from_below:
                        # Price hit resistance from below → fade short
                        side = "short"
                        entry = level - 0.003  # 3 pips below the level
                        stop = level + STOP_PIPS
                        target = entry - TARGET_PIPS
                    else:
                        # Price hit support from above → fade long
                        side = "long"
                        entry = level + 0.003  # 3 pips above the level
                        stop = level - STOP_PIPS
                        target = entry + TARGET_PIPS

                    expected_edge = TARGET_PIPS - estimated_cost
                    confidence = min(0.85, 0.5 + (atr_daily - MIN_ATR) * 0.5)
                    regime_fit = min(1.0, max(-1.0, (atr_daily - MIN_ATR) / MIN_ATR))

                    candidates.append(
                        Candidate(
                            strategy_id=STRATEGY_ID,
                            symbol="USDJPY",
                            side=side,
                            entry=round(entry, 3),
                            stop=round(stop, 3),
                            target=round(target, 3),
                            expected_edge=round(expected_edge, 6),
                            estimated_cost=round(estimated_cost, 6),
                            confidence=round(confidence, 4),
                            expected_holding_minutes=45,
                            portfolio_group=PORTFOLIO_GROUP,
                            exposure_bucket=EXPOSURE_BUCKET,
                            regime_fit=round(regime_fit, 4),
                            timestamp=utc_ts,
                        )
                    )
                    self._bars_since_signal = 0
                    break  # one signal per bar max

            level += 0.5

        yield from candidates


__all__ = ["RoundNumberRejectionStrategy"]
