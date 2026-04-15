"""Realistic round-trip cost model — the entry point for CI gate I3.

Reads ``config/execution.yaml`` and returns a :class:`RoundTripCost` for a
given symbol / side / session / timestamp / holding window. Every strategy
that computes ``Candidate.estimated_cost`` pulls its number from this
module; constants and ad-hoc values are forbidden (enforced by reviews and
the contract-guard agent).

Phase 2 implementation. This skeleton exists so:

* ``config/execution.yaml`` has a consumer and does not drift into YAML-rot.
* Tests in ``tests/contracts/test_cost.py`` have an import target to swap
  from skipped to active as components land.
* The admission layer can start wiring against the shape now, before the
  body is filled in.

The prior ``src/backtest/paper_poc.py`` hardcoded spread/slippage/commission
defaults at zero; this module's whole purpose is to replace that with a
config-driven, realistic model that costs swap, weekend gap, and a session
× liquidity × side slippage distribution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml

__all__ = [
    "CostConfigError",
    "ExecutionCostConfig",
    "RoundTripCost",
    "load_execution_cost_config",
    "round_trip_cost",
]


DEFAULT_EXECUTION_YAML = Path("config") / "execution.yaml"


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


def round_trip_cost(
    *,
    config: ExecutionCostConfig,
    symbol: str,
    side: Literal["long", "short"],
    timestamp: datetime,
    expected_holding_minutes: int,
) -> RoundTripCost:
    """Compute the realistic round-trip cost for a candidate.

    Phase 2 will fill in the body: pull the spread curve for ``(symbol,
    session)`` at ``timestamp``, sample a slippage draw from the configured
    distribution keyed on ``(symbol, session, side)``, apply a per-contract
    commission, charge swap for any rollover crossed by
    ``expected_holding_minutes``, and add a weekend-gap premium if the
    holding window straddles a weekend.

    Until the body lands, this raises ``NotImplementedError`` so accidental
    production calls fail loudly instead of silently returning zero.
    """

    raise NotImplementedError(
        "round_trip_cost body lands in Phase 2 — config loader is wired, "
        "cost computation pending. See tests/contracts/test_cost.py."
    )
