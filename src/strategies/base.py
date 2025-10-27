"""Strategy plugin contracts for deterministic signal generation.

The dataclasses and protocols exported here codify the Strategy Plugin
interface described in :mod:`detailed_design_fx_signal_tool_v1` §3.5.5
(``PKG-STRAT-IFACE-01``).  They intentionally avoid business logic so
that downstream registries and pipelines can enforce contracts without
coupling to concrete implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Iterable, Protocol, Sequence, runtime_checkable

from src.execution import SpreadCooldownState


class FeatureContext(Protocol):
    """Minimal contract for feature access used in strategy metadata checks."""

    available_keys: frozenset[str]

    def lookup(self, *, symbol: str, feature: str, timeframe: str) -> Any: ...

    def get_latest(self, *, symbol: str, feature: str, timeframe: str) -> Any: ...


class RegimeState(Protocol):
    """Placeholder protocol for regime detector output."""

    mode: str


class NewsGateState(Protocol):
    """News blackout status for the current symbol universe."""

    blocked: bool
    reason: str | None
    release_ts: Any | None


class CalendarGateState(Protocol):
    """Calendar-derived restrictions including holiday windows."""

    blocked: bool
    holiday_block: bool
    reason: str | None


class SpreadGateState(Protocol):
    """Spread-driven throttling state shared with strategies."""

    state: SpreadCooldownState
    reason: str | None
    cooldown_eta: Any | None


class MarketGateState(Protocol):
    """Composite market gating decisions (news/calendar/spread)."""

    news: NewsGateState
    calendar: CalendarGateState
    spread: SpreadGateState


class RiskGateState(Protocol):
    """Risk guardrails that affect order submission."""

    reduce_only: bool
    reduce_only_reason: str | None


class HumanGateState(Protocol):
    """Human-in-the-loop constraints required for ticket approval."""

    double_entry_required: bool
    required_roles: Sequence[str]
    acknowledged_roles: Sequence[str]
    ack_deadline: Any | None
    manual_comment_required: bool
    comment_min_length: int


class GateState(Protocol):
    """Placeholder protocol for aggregated gate state."""

    market: MarketGateState
    risk: RiskGateState
    human: HumanGateState


class AccountState(Protocol):
    """Placeholder protocol for account metrics surfaced to strategies."""

    equity: float


class ConfigSnapshot(Protocol):
    """Placeholder protocol for immutable configuration view."""

    cfg_hash: str


class MarketClock(Protocol):
    """Placeholder protocol for deterministic clock information."""

    now: Any
    timeframe: str


class RawSignal(Protocol):
    """Placeholder protocol for raw strategy signals."""

    strategy_id: str


@dataclass(slots=True, frozen=True)
class StrategyContext:
    """Shared, immutable services handed to strategy plugins.

    ``StrategyEngine`` constructs one context per evaluation cycle so
    that plugins observe a deterministic snapshot of upstream state.  The
    fields mirror the design contract and allow Codex prompts/tests to
    reason about the strategy environment without relying on concrete
    implementations.
    """

    features: FeatureContext
    """Feature frame accessor populated by :class:`FeaturePipeline`."""

    regime: RegimeState
    """Regime detector snapshot (volatility/trend modes)."""

    gate: GateState
    """Aggregated gate state (calendar, spread, board mode blocks)."""

    account: AccountState
    """Account metrics such as equity, margin availability, and staleness."""

    config: ConfigSnapshot
    """Read-only configuration snapshot with change hashes for auditing."""

    watchlist: frozenset[str]
    """Effective set of symbols the strategy is allowed to monitor."""

    clock: MarketClock
    """Trading calendar context including ``now`` and ``timeframe``."""

    seed: int
    """Deterministic seed derived from mode context and strategy metadata."""


@dataclass(slots=True, frozen=True)
class StrategyMetadata:
    """Static metadata surfaced by strategy plugins."""

    name: str
    version: str
    required_features: frozenset[str]
    tags: frozenset[str] = field(default_factory=frozenset)
    seed_offset: int = 0

    def is_applicable(self, context: StrategyContext) -> bool:
        """Return ``True`` when all required features are available."""

        return self.required_features.issubset(context.features.available_keys)


@runtime_checkable
class StrategyPluginProtocol(Protocol):
    """Protocol that every strategy plugin must satisfy.

    The attributes and call signatures mirror the design contract so the
    registry can validate plugins via :func:`isinstance` checks.
    """

    id: ClassVar[str]
    metadata: StrategyMetadata

    def required_warmup_bars(self) -> int:
        """Return the minimum warm-up bars needed before evaluation."""

    def cooldown_bars(self) -> int:
        """Return the number of bars to skip after emitting a signal."""

    def evaluate(self, context: StrategyContext) -> Iterable[RawSignal]:
        """Evaluate the strategy for the supplied context."""


# ---------------------------------------------------------------------------
# Backwards compatibility
# ---------------------------------------------------------------------------
#
# ``Strategy`` previously exposed a simplified protocol that returned a
# bespoke ``StrategySignal`` dataclass.  The implementation packet
# ``PKG-STRAT-IFACE-01`` superseded that contract in favour of
# ``StrategyPluginProtocol``/``StrategyMetadata``.  The alias remains so
# that legacy imports continue to resolve while downstream code migrates
# to the new names.
Strategy = StrategyPluginProtocol


__all__ = [
    "StrategyContext",
    "StrategyMetadata",
    "StrategyPluginProtocol",
    "Strategy",
]
