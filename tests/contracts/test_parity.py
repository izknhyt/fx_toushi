"""CI gate I2 — Parity: backtest / shadow / live share one decision path.

See ``docs/invariants.md`` §I2 and ``docs/architecture.md`` §2 / §3.

The parity test replays a fixed-seed, canned input window through each of
the three modes and asserts the resulting admission decisions are
byte-identical. The decision path is centralised at
``src/decision_path.py`` (landing in Phase 2).

This file is the CI slot. Each skipped test becomes active as the referenced
component lands.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason=(
        "Phase 2: requires src/decision_path.py + fixed fixture window. "
        "Once both exist, replay backtest and shadow modes against the same "
        "bars and seed, then assert admission decisions are identical."
    )
)
def test_backtest_shadow_decision_parity() -> None:  # pragma: no cover - pending
    raise NotImplementedError


@pytest.mark.skip(
    reason=(
        "Phase 2: once a dry-live mode exists, replay the same fixture and "
        "assert live admission decisions match backtest byte-for-byte."
    )
)
def test_backtest_live_decision_parity() -> None:  # pragma: no cover - pending
    raise NotImplementedError


@pytest.mark.skip(
    reason=(
        "Phase 2: strategies route candidates only through decision_path; "
        "any direct execution call bypassing it breaks parity."
    )
)
def test_no_mode_specific_shortcut() -> None:  # pragma: no cover - pending
    raise NotImplementedError
