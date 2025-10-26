"""Strategy plugin contracts and shared dataclasses."""

from .base import Strategy, StrategyContext, StrategySignal

__all__ = [
    "Strategy",
    "StrategyContext",
    "StrategySignal",
]
