"""Protocols and lightweight dataclasses for execution modelling.

The production implementation will evolve into a deterministic execution
model that applies human delay, spread state, and broker rules to raw
strategy signals.  The scaffolding here mirrors the API contracts from
``detailed_design_fx_signal_tool_v1.md`` so that other packages and tests
can type-check against them while the heavy lifting is developed in
future packets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable

from typing_extensions import Literal

EntryMode = Literal["market", "marketable_limit", "limit_requote"]
"""Enumeration of strategy-requested entry modes from the design contract."""

FillStyle = Literal["ioc", "fok", "gtd"]
"""Abstract fill execution semantics surfaced to downstream components."""

FillPolicy = Literal["ioc", "fok", "gtd", "day"]
"""Policy hints consumed by the order router and ticket builder.

``"fok"`` and ``"gtd"`` align with :data:`FillStyle` to carry venue specific
semantics alongside the higher level execution hints.
"""


@dataclass(slots=True, frozen=True)
class ExecutionAdjustments:
    """Deterministic adjustments derived from the execution model.

    The fields intentionally capture the data that downstream components
    (risk manager, position sizer, ticket builder) consume.  They mirror
    the detailed design but default to ``None``/sentinel values so the
    scaffolding can be instantiated in tests without requiring market
    data.
    """

    expected_entry: float | None
    """Price the strategy should expect after delay/slippage corrections."""

    expected_slippage: float | None
    """Projected slippage in pips or price units depending on the venue."""

    ttl_seconds: int
    """Good-until time in seconds for IOC/limit style routing."""

    fill_style: FillStyle
    """High level fill semantic (IOC, GTD, etc.)."""

    fill_policy: FillPolicy | None = None
    """Optional routing hint for downstream adapters."""

    mode_label: str | None = None
    """Human readable label surfaced on tickets and dashboards."""

    drift_guard_r: float | None = None
    """Optional drift guard threshold expressed in risk R units."""


class ExecutionError(RuntimeError):
    """Base error for execution model scaffolding."""


class ExecutionConfigError(ExecutionError):
    """Raised when execution configuration validation fails."""


class ExecutionRuleViolation(ExecutionError):
    """Raised when a signal violates execution guardrails."""


@runtime_checkable
class ExecutionModelProtocol(Protocol):
    """Protocol describing the public API of the execution model."""

    def apply(
        self,
        signal: Any,
        market_snapshot: Mapping[str, Any],
        *,
        spread_state: Any,
        mode_context: Mapping[str, Any] | None = None,
    ) -> ExecutionAdjustments:
        """Apply execution adjustments to a raw strategy signal."""

    def validate_config(self, config: Mapping[str, Any]) -> None:
        """Validate execution model configuration data."""

    def apply_human_delay(self, *, seed: int) -> float:
        """Return the simulated human delay in seconds for deterministic tests."""


__all__ = [
    "EntryMode",
    "ExecutionAdjustments",
    "ExecutionError",
    "ExecutionConfigError",
    "ExecutionModelProtocol",
    "ExecutionRuleViolation",
    "FillPolicy",
    "FillStyle",
]
