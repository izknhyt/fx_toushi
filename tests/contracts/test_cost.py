"""CI gate I3 — Cost positivity.

See ``docs/invariants.md`` §I3 and ``docs/architecture.md`` §2.

For every non-zero configuration of ``config/execution.yaml`` (spread,
slippage, commission, swap, weekend gap), a round-trip trade must produce
``realized_cost > 0``. A zero-cost round trip is a bug — the bar at which
cost must be modelled honestly is the bar at which any backtest number is
meaningful.

This file is the CI slot. Tests activate as ``src/execution/cost.py`` lands
in Phase 2.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason=(
        "Phase 2: once src/execution/cost.py reads config/execution.yaml, "
        "parametrise over every cost dimension (spread curve / slippage "
        "distribution / commission / swap / weekend gap) and assert that a "
        "round-trip trade under non-zero settings yields realized_cost > 0."
    )
)
def test_spread_non_zero_yields_positive_cost() -> None:  # pragma: no cover - pending
    raise NotImplementedError


@pytest.mark.skip(
    reason="Phase 2: slippage distribution sampled through round-trip must cost > 0."
)
def test_slippage_non_zero_yields_positive_cost() -> None:  # pragma: no cover - pending
    raise NotImplementedError


@pytest.mark.skip(
    reason="Phase 2: overnight swap charged on holdings crossing rollover must cost > 0."
)
def test_swap_non_zero_yields_positive_cost() -> None:  # pragma: no cover - pending
    raise NotImplementedError


@pytest.mark.skip(
    reason="Phase 2: weekend gap cost on positions held through weekend must cost > 0."
)
def test_weekend_gap_non_zero_yields_positive_cost() -> None:  # pragma: no cover - pending
    raise NotImplementedError


@pytest.mark.skip(
    reason=(
        "Phase 2: exhaustively sweep every leaf under config/execution.yaml "
        "and assert there is no path where round-trip cost collapses to 0."
    )
)
def test_no_zero_cost_paths_in_execution_config() -> None:  # pragma: no cover - pending
    raise NotImplementedError
