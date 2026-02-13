"""Default strategy plugin catalog used by research and PoC tooling."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from src.strategies.base import StrategyPluginProtocol
from src.strategies.asia_compression_expansion_breakout import (
    AsiaCompressionExpansionBreakoutStrategy,
)
from src.strategies.donchian import (
    DonchianBreakoutLongOnlyStrategy,
    DonchianBreakoutStrategy,
    DonchianBreakoutUpperOnlyStrategy,
)
from src.strategies.ma_rsi import MovingAverageRsiStrategy
from src.strategies.us_orb_vwap_retest import UsOpeningRangeBreakoutVwapRetestStrategy
from src.strategies.us_session_momentum import UsSessionTrendPullbackStrategy

StrategyBuilder = Callable[[], StrategyPluginProtocol]


def default_strategy_builders() -> tuple[StrategyBuilder, ...]:
    """Return the built-in strategy constructors."""

    return (
        MovingAverageRsiStrategy,
        DonchianBreakoutStrategy,
        DonchianBreakoutLongOnlyStrategy,
        DonchianBreakoutUpperOnlyStrategy,
        AsiaCompressionExpansionBreakoutStrategy,
        UsSessionTrendPullbackStrategy,
        UsOpeningRangeBreakoutVwapRetestStrategy,
    )


def build_default_plugins() -> dict[str, StrategyPluginProtocol]:
    """Instantiate and index default strategy plugins by strategy id."""

    plugins: dict[str, StrategyPluginProtocol] = {}
    for builder in default_strategy_builders():
        plugin = builder()
        if plugin.id in plugins:
            raise ValueError(f"Duplicate strategy id in plugin catalog: {plugin.id}")
        plugins[plugin.id] = plugin
    return plugins


def apply_manifest_parameters(
    plugin: StrategyPluginProtocol,
    *,
    parameters: Mapping[str, Any] | None = None,
) -> None:
    """Apply optional parameter overrides to plugin instance state."""

    if not isinstance(plugin, MovingAverageRsiStrategy):
        return
    params = parameters if isinstance(parameters, Mapping) else {}
    entry = params.get("entry")
    entry_params = entry if isinstance(entry, Mapping) else {}
    plugin.rsi_long_threshold = float(
        entry_params.get("rsi_long_threshold", plugin.rsi_long_threshold)
    )
    plugin.rsi_short_threshold = float(
        entry_params.get("rsi_short_threshold", plugin.rsi_short_threshold)
    )
    plugin.min_gap_pct = float(entry_params.get("min_gap_pct", plugin.min_gap_pct))
    plugin._cooldown_bars = int(entry_params.get("cooldown_bars", plugin.cooldown_bars()))


__all__ = [
    "StrategyBuilder",
    "default_strategy_builders",
    "build_default_plugins",
    "apply_manifest_parameters",
]
