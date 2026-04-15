"""Candidate trade contract — the only type strategies may emit.

Every strategy plugin registered under ``config/strategy.yaml`` must produce
:class:`Candidate` instances. The admission layer consumes only this type and
never falls back to loose dicts or legacy payloads. The 14 required fields
are enumerated here and enforced by :func:`validate_candidate`; the contract
test under ``tests/contracts/test_candidate_contract.py`` (CI gate **I1**)
refuses to green unless every emitted candidate passes validation.

See ``docs/invariants.md`` §I1 and ``docs/architecture.md`` §2 for the
contract in context.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from typing import Literal

__all__ = [
    "Candidate",
    "CandidateContractError",
    "Side",
    "validate_candidate",
]


Side = Literal["long", "short"]


@dataclass(frozen=True, slots=True)
class Candidate:
    """A single candidate trade emitted by a strategy plugin.

    All 14 fields are required. The admission layer uses these fields (and
    only these fields) to decide ``accept`` / ``reject`` / ``defer`` /
    ``resize`` / ``replace``. Strategies must not leak additional signal
    metadata through side channels — if admission needs more, the field
    belongs in this contract.
    """

    strategy_id: str
    symbol: str
    side: Side
    entry: float
    stop: float
    target: float
    expected_edge: float
    estimated_cost: float
    confidence: float
    expected_holding_minutes: int
    portfolio_group: str
    exposure_bucket: str
    regime_fit: float
    timestamp: datetime


class CandidateContractError(ValueError):
    """Raised by :func:`validate_candidate` when a contract rule is violated."""


def _require_str(name: str, value: object) -> None:
    if not isinstance(value, str) or not value:
        raise CandidateContractError(
            f"{name} must be a non-empty str, got {value!r}"
        )


def _require_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CandidateContractError(
            f"{name} must be numeric (int or float), got {type(value).__name__}"
        )
    return float(value)


def validate_candidate(candidate: Candidate) -> None:
    """Validate a :class:`Candidate` against the 14-field contract.

    Raises :class:`CandidateContractError` on the first violation. Intended
    to be called on every candidate emitted by a strategy during the
    contract test, on admission-layer input in production, and on any
    deserialization boundary that yields a :class:`Candidate`.

    Rules enforced:

    * Required type is :class:`Candidate`; no duck typing.
    * String fields (``strategy_id``, ``symbol``, ``portfolio_group``,
      ``exposure_bucket``) are non-empty ``str``.
    * ``side`` is exactly ``"long"`` or ``"short"``.
    * Numeric fields are numeric (``int``/``float``, never ``bool``).
    * ``confidence`` is within ``[0.0, 1.0]``.
    * ``regime_fit`` is within ``[-1.0, 1.0]``.
    * ``expected_holding_minutes`` is a positive ``int``.
    * ``timestamp`` is a timezone-aware :class:`datetime`.
    * For ``side="long"``: ``stop < entry < target``.
    * For ``side="short"``: ``target < entry < stop``.

    These rules are the bare minimum a candidate must satisfy to participate
    in admission scoring. Strategy-specific richer validation lives in the
    strategy's own unit tests.
    """

    if not isinstance(candidate, Candidate):
        raise CandidateContractError(
            f"expected Candidate, got {type(candidate).__name__}"
        )

    # String identity fields.
    _require_str("strategy_id", candidate.strategy_id)
    _require_str("symbol", candidate.symbol)
    _require_str("portfolio_group", candidate.portfolio_group)
    _require_str("exposure_bucket", candidate.exposure_bucket)

    # Side.
    if candidate.side not in ("long", "short"):
        raise CandidateContractError(
            f"side must be 'long' or 'short', got {candidate.side!r}"
        )

    # Numeric price/edge/cost fields.
    entry = _require_number("entry", candidate.entry)
    stop = _require_number("stop", candidate.stop)
    target = _require_number("target", candidate.target)
    _require_number("expected_edge", candidate.expected_edge)
    estimated_cost = _require_number("estimated_cost", candidate.estimated_cost)

    if estimated_cost < 0.0:
        raise CandidateContractError(
            f"estimated_cost must be >= 0, got {estimated_cost}"
        )

    # Confidence bounded to [0, 1].
    confidence = _require_number("confidence", candidate.confidence)
    if not 0.0 <= confidence <= 1.0:
        raise CandidateContractError(
            f"confidence must be within [0.0, 1.0], got {confidence}"
        )

    # Regime fit bounded to [-1, 1].
    regime_fit = _require_number("regime_fit", candidate.regime_fit)
    if not -1.0 <= regime_fit <= 1.0:
        raise CandidateContractError(
            f"regime_fit must be within [-1.0, 1.0], got {regime_fit}"
        )

    # Holding window positive integer.
    if (
        isinstance(candidate.expected_holding_minutes, bool)
        or not isinstance(candidate.expected_holding_minutes, int)
        or candidate.expected_holding_minutes <= 0
    ):
        raise CandidateContractError(
            "expected_holding_minutes must be a positive int, got "
            f"{candidate.expected_holding_minutes!r}"
        )

    # Timestamp must be tz-aware datetime for parity replay.
    if not isinstance(candidate.timestamp, datetime):
        raise CandidateContractError(
            "timestamp must be a datetime, got "
            f"{type(candidate.timestamp).__name__}"
        )
    if candidate.timestamp.tzinfo is None:
        raise CandidateContractError(
            "timestamp must be timezone-aware (UTC preferred)"
        )

    # Price-side invariants.
    if candidate.side == "long":
        if not (stop < entry < target):
            raise CandidateContractError(
                "long candidate requires stop < entry < target, got "
                f"stop={stop}, entry={entry}, target={target}"
            )
    else:
        if not (target < entry < stop):
            raise CandidateContractError(
                "short candidate requires target < entry < stop, got "
                f"target={target}, entry={entry}, stop={stop}"
            )


def required_field_names() -> tuple[str, ...]:
    """Return the ordered tuple of required field names.

    Kept as a thin helper so test collectors and schema generators can
    iterate the canonical field list without re-importing ``dataclasses``.
    """

    return tuple(f.name for f in fields(Candidate))
