"""CI gate I1 — Candidate contract.

Every strategy registered under ``config/strategy.yaml`` must emit
:class:`src.contract.Candidate` objects with all 14 required fields
validated by :func:`src.contract.validate_candidate`. This test is the
skeleton; strategies migrate into the loop as Phase 2/3 lands.

See ``docs/invariants.md`` §I1 and ``docs/architecture.md`` §2.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.contract import (
    Candidate,
    CandidateContractError,
    required_field_names,
    validate_candidate,
)


def _sample_long() -> Candidate:
    """A minimal valid long candidate used by positive-path assertions."""

    return Candidate(
        strategy_id="sample",
        symbol="USDJPY",
        side="long",
        entry=150.10,
        stop=149.80,
        target=150.80,
        expected_edge=0.0025,
        estimated_cost=0.0004,
        confidence=0.55,
        expected_holding_minutes=45,
        portfolio_group="mean_reversion",
        exposure_bucket="jpy_intraday",
        regime_fit=0.3,
        timestamp=datetime(2026, 4, 15, 9, 0, tzinfo=timezone.utc),
    )


def _sample_short() -> Candidate:
    return Candidate(
        strategy_id="sample",
        symbol="USDJPY",
        side="short",
        entry=150.10,
        stop=150.40,
        target=149.40,
        expected_edge=0.0028,
        estimated_cost=0.0004,
        confidence=0.60,
        expected_holding_minutes=30,
        portfolio_group="mean_reversion",
        exposure_bucket="jpy_intraday",
        regime_fit=-0.2,
        timestamp=datetime(2026, 4, 15, 9, 0, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Contract shape
# ---------------------------------------------------------------------------


def test_candidate_has_14_required_fields() -> None:
    """The contract is 14 fields exactly — no drift without charter amendment."""

    assert len(required_field_names()) == 14


def test_valid_long_candidate_passes() -> None:
    validate_candidate(_sample_long())


def test_valid_short_candidate_passes() -> None:
    validate_candidate(_sample_short())


# ---------------------------------------------------------------------------
# Rejection cases
# ---------------------------------------------------------------------------


def test_non_candidate_input_rejected() -> None:
    with pytest.raises(CandidateContractError):
        validate_candidate({"strategy_id": "sample"})  # type: ignore[arg-type]


def test_empty_strategy_id_rejected() -> None:
    bad = _sample_long().__class__(
        **{**_sample_long().__dict__, "strategy_id": ""}
    )
    with pytest.raises(CandidateContractError, match="strategy_id"):
        validate_candidate(bad)


def test_bad_side_rejected() -> None:
    bad = _sample_long().__class__(
        **{**_sample_long().__dict__, "side": "flat"}
    )
    with pytest.raises(CandidateContractError, match="side"):
        validate_candidate(bad)


def test_long_with_inverted_prices_rejected() -> None:
    """stop must be below entry for a long — no exceptions."""

    bad = _sample_long().__class__(
        **{**_sample_long().__dict__, "stop": 150.50}
    )
    with pytest.raises(CandidateContractError, match="long"):
        validate_candidate(bad)


def test_short_with_inverted_prices_rejected() -> None:
    bad = _sample_short().__class__(
        **{**_sample_short().__dict__, "stop": 149.90}
    )
    with pytest.raises(CandidateContractError, match="short"):
        validate_candidate(bad)


def test_confidence_out_of_range_rejected() -> None:
    bad = _sample_long().__class__(
        **{**_sample_long().__dict__, "confidence": 1.2}
    )
    with pytest.raises(CandidateContractError, match="confidence"):
        validate_candidate(bad)


def test_regime_fit_out_of_range_rejected() -> None:
    bad = _sample_long().__class__(
        **{**_sample_long().__dict__, "regime_fit": -1.5}
    )
    with pytest.raises(CandidateContractError, match="regime_fit"):
        validate_candidate(bad)


def test_negative_holding_minutes_rejected() -> None:
    bad = _sample_long().__class__(
        **{**_sample_long().__dict__, "expected_holding_minutes": 0}
    )
    with pytest.raises(CandidateContractError, match="expected_holding_minutes"):
        validate_candidate(bad)


def test_naive_timestamp_rejected() -> None:
    bad = _sample_long().__class__(
        **{**_sample_long().__dict__, "timestamp": datetime(2026, 4, 15, 9, 0)}
    )
    with pytest.raises(CandidateContractError, match="timezone-aware"):
        validate_candidate(bad)


def test_negative_estimated_cost_rejected() -> None:
    bad = _sample_long().__class__(
        **{**_sample_long().__dict__, "estimated_cost": -0.0001}
    )
    with pytest.raises(CandidateContractError, match="estimated_cost"):
        validate_candidate(bad)


# ---------------------------------------------------------------------------
# Strategy registry sweep — stub until Phase 3 migration
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "Phase 2/3: once config/strategy.yaml lists strategies that emit "
        "Candidate, this loop iterates them and validates every emission. "
        "Until then, the unit rules above keep the contract honest."
    )
)
def test_every_registered_strategy_emits_valid_candidates() -> None:  # pragma: no cover - pending
    raise NotImplementedError
