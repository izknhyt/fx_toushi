"""Diagnostics package."""

from .broker.api_fault_lab import FaultScenario, simulate_fault

__all__ = ["FaultScenario", "simulate_fault"]
