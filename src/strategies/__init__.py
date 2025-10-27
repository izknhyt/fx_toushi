"""Strategy plugin contracts and shared dataclasses."""

from .base import Strategy, StrategyContext, StrategyMetadata, StrategyPluginProtocol

__all__ = [
    "Strategy",
    "StrategyContext",
    "StrategyMetadata",
    "StrategyPluginProtocol",
]
