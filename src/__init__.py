"""Top-level package for the FX human-in-the-loop trading tool.

The exports below establish the canonical import paths used throughout
M1 and later milestones. Keeping these stable prevents churn in Codex
prompts and follow-up pull requests.
"""

__all__ = [
    "app",
    "interfaces",
    "core",
    "data",
    "features",
    "strategies",
    "ticket",
    "risk",
    "infra",
    "persistence",
    "brokers",
]
