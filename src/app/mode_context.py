"""Mode context scaffolding for SessionManager bootstrap tests.

This module implements the minimal scaffolding required by
``CHK-0.6.9-6``/``CHK-0.6.9-7`` so that the project can instantiate
:class:`ModeContext` objects from ``config/profiles/*.yaml``.
The implementations intentionally favour immutability and
deterministic behaviour to make the upcoming SessionManager
bootstrap scripts reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence
from typing import Literal
from types import MappingProxyType

from yaml import safe_load

__all__ = [
    "AccountGateway",
    "AuditChannel",
    "DataFeedBundle",
    "ExecutionProfile",
    "MarketClock",
    "ModeContext",
    "ModeContextFactory",
    "ModeProfile",
]

ProfileMode = Literal["backtest", "paper", "live"]


def _freeze(value: Any) -> Any:
    """Return an immutable representation of ``value`` suitable for storage.

    The helper recursively converts dictionaries into mapping proxies and
    lists into tuples so that :class:`ModeProfile` exposes a read-only view
    of the profile payload.  Primitive values are returned unchanged.
    """

    if isinstance(value, MutableMapping):
        frozen = {key: _freeze(val) for key, val in value.items()}
        return MappingProxyType(frozen)
    if isinstance(value, Mapping):
        frozen = {key: _freeze(val) for key, val in value.items()}
        return MappingProxyType(frozen)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(slots=True, frozen=True)
class ModeProfile:
    """Immutable view over a mode profile configuration payload."""

    profile_id: str
    mode: ProfileMode
    schema_version: str | int | None
    metadata: Mapping[str, Any]
    data_ingestion: Mapping[str, Any]
    timeframes: Mapping[str, Any]
    risk: Mapping[str, Any]
    gates: Mapping[str, Any]
    strategies: tuple[Mapping[str, Any], ...]
    execution: Mapping[str, Any]
    spread: Mapping[str, Any]
    funding: Mapping[str, Any]
    correlation: Mapping[str, Any]
    scheduler: Mapping[str, Any]
    raw: Mapping[str, Any]
    source: Path

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any], *, source: Path) -> "ModeProfile":
        """Construct a profile from a YAML payload."""

        required_keys = {
            "profile_id",
            "mode",
            "schema_version",
            "data_ingestion",
            "timeframes",
            "risk",
            "gates",
            "strategies",
            "execution",
            "spread",
            "funding",
            "correlation",
            "scheduler",
        }
        missing = sorted(key for key in required_keys if key not in payload)
        if missing:
            raise ValueError(f"Profile payload missing required keys: {missing}")

        mode = payload["mode"]
        if mode not in {"backtest", "paper", "live"}:
            raise ValueError(f"Unsupported mode value: {mode!r}")

        strategies_payload = payload.get("strategies")
        if not isinstance(strategies_payload, Sequence) or not strategies_payload:
            raise ValueError("Profile strategies must contain at least one entry")

        frozen_payload = _freeze(payload)

        return cls(
            profile_id=str(payload["profile_id"]),
            mode=mode,
            schema_version=payload.get("schema_version"),
            metadata=_freeze(payload.get("metadata", {})),
            data_ingestion=_freeze(payload["data_ingestion"]),
            timeframes=_freeze(payload["timeframes"]),
            risk=_freeze(payload["risk"]),
            gates=_freeze(payload["gates"]),
            strategies=tuple(_freeze(entry) for entry in strategies_payload),
            execution=_freeze(payload["execution"]),
            spread=_freeze(payload["spread"]),
            funding=_freeze(payload["funding"]),
            correlation=_freeze(payload["correlation"]),
            scheduler=_freeze(payload["scheduler"]),
            raw=frozen_payload,
            source=source,
        )


@dataclass(slots=True, frozen=True)
class MarketClock:
    """Minimal deterministic clock representation used during bootstrap."""

    mode: ProfileMode
    timeframe: str
    timezone: str


@dataclass(slots=True, frozen=True)
class DataFeedBundle:
    """Collection of data feed configuration derived from a profile."""

    primary: str
    fallbacks: tuple[str, ...]
    poll_interval_sec: int | None
    catch_up_enabled: bool
    manual_fallback_allowed: bool
    sla_threshold_profile: str | None


@dataclass(slots=True, frozen=True)
class ExecutionProfile:
    """Execution tuning extracted from the profile payload."""

    slippage_bps: float | int | None
    latency_simulation_ms: float | int | None
    additional_settings: Mapping[str, Any]


@dataclass(slots=True, frozen=True)
class AccountGateway:
    """Stub representation of the account gateway for each mode."""

    mode: ProfileMode
    profile_id: str


@dataclass(slots=True, frozen=True)
class AuditChannel:
    """Stub representation of audit stream wiring for tests."""

    profile_id: str
    streams: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class ModeContext:
    """Aggregate container built from a :class:`ModeProfile`."""

    mode: ProfileMode
    profile: ModeProfile
    clock: MarketClock
    deterministic_seed: int
    data_feeds: DataFeedBundle
    execution_profile: ExecutionProfile
    account_gateway: AccountGateway
    audit_channel: AuditChannel


class ModeContextFactory:
    """Factory that wires profile YAML into :class:`ModeContext` instances."""

    def __init__(self, *, profiles_dir: Path | str | None = None) -> None:
        self._profiles_dir = Path(profiles_dir or Path("config") / "profiles").resolve()

    def create(self, profile_name: str, *, session_id: str) -> ModeContext:
        """Build a :class:`ModeContext` for ``profile_name`` and ``session_id``."""

        profile = self.load_profile(profile_name)
        clock = MarketClock(
            mode=profile.mode,
            timeframe=str(profile.timeframes.get("trigger", "")),
            timezone=str(profile.scheduler.get("timezone", "UTC")),
        )
        ingestion = profile.data_ingestion
        fallbacks = ingestion.get("fallback_providers")
        if isinstance(fallbacks, Sequence) and not isinstance(fallbacks, (str, bytes, bytearray)):
            fallback_tuple = tuple(str(item) for item in fallbacks)
        else:
            fallback_tuple = tuple()

        data_feeds = DataFeedBundle(
            primary=str(ingestion.get("provider", "")),
            fallbacks=fallback_tuple,
            poll_interval_sec=(
                int(ingestion["poll_interval_sec"])
                if "poll_interval_sec" in ingestion
                else None
            ),
            catch_up_enabled=bool(ingestion.get("catch_up_enabled", False)),
            manual_fallback_allowed=bool(ingestion.get("manual_fallback_allowed", False)),
            sla_threshold_profile=(
                str(ingestion.get("sla_threshold_profile"))
                if ingestion.get("sla_threshold_profile") is not None
                else None
            ),
        )

        execution_payload = profile.execution
        execution_profile = ExecutionProfile(
            slippage_bps=execution_payload.get("slippage_bps"),
            latency_simulation_ms=execution_payload.get("latency_simulation_ms"),
            additional_settings=_freeze(
                {key: value for key, value in execution_payload.items() if key not in {"slippage_bps", "latency_simulation_ms"}}
            ),
        )

        account_gateway = AccountGateway(mode=profile.mode, profile_id=profile.profile_id)
        audit_channel = AuditChannel(
            profile_id=profile.profile_id,
            streams=("session", "signals", "execution"),
        )

        deterministic_seed = self._derive_seed(profile=profile, session_id=session_id)

        return ModeContext(
            mode=profile.mode,
            profile=profile,
            clock=clock,
            deterministic_seed=deterministic_seed,
            data_feeds=data_feeds,
            execution_profile=execution_profile,
            account_gateway=account_gateway,
            audit_channel=audit_channel,
        )

    def load_profile(self, profile_name: str) -> ModeProfile:
        """Return a cached :class:`ModeProfile` for ``profile_name``."""

        return self._load_profile_cached(profile_name)

    @lru_cache(maxsize=16)
    def _load_profile_cached(self, profile_name: str) -> ModeProfile:
        path = self._profiles_dir / f"{profile_name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Profile configuration not found: {path}")
        payload = safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError(f"Profile YAML at {path} must contain a mapping root")
        return ModeProfile.from_mapping(payload, source=path)

    @staticmethod
    def _derive_seed(*, profile: ModeProfile, session_id: str) -> int:
        """Derive a deterministic integer seed from the profile/session pair."""

        digest = hashlib.blake2b(digest_size=16)
        digest.update(profile.profile_id.encode("utf-8"))
        digest.update(profile.mode.encode("utf-8"))
        digest.update(str(profile.schema_version).encode("utf-8"))
        digest.update(session_id.encode("utf-8"))
        return int.from_bytes(digest.digest(), "big")


