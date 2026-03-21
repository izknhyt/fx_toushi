"""Compatibility wrapper for the canonical candidate onboarding runner."""

from __future__ import annotations

from tools.run_portfolio_candidate_onboarding import main, run_candidate_onboarding

__all__ = ["main", "run_candidate_onboarding"]


if __name__ == "__main__":
    raise SystemExit(main())
