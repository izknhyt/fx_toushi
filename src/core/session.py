"""Session lifecycle management primitives.

This module defines the contracts that orchestrate the
lifecycle of a trading session. The abstractions capture how the
application coordinates configuration, telemetry, and workflow
activation so that downstream components can remain deterministic
and mode-aware.  The module also contains the minimal :class:`ModeContext`
scaffolding required by smoke tests and runbook drills so that
``config/profiles/<mode>.yaml`` can be deterministically replayed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping, MutableMapping, Optional, Protocol
from typing import Sequence, runtime_checkable
from typing import Literal

from yaml import safe_load

if TYPE_CHECKING:  # pragma: no cover - import cycle guard for type checking only
    from .workflow import WorkflowContext, WorkflowOrchestrator, WorkflowResult

__all__ = [
    "AccountGateway",
    "AuditChannel",
    "DataFeedBundle",
    "ExecutionProfile",
    "MarketClock",
    "ModeContext",
    "ModeContextFactory",
    "ModeProfile",
    "SessionConfig",
    "SessionContext",
    "SessionManager",
    "DefaultSessionManager",
    "create_session_context",
]

ProfileMode = Literal["backtest", "paper", "live"]


def _freeze(value: Any) -> Any:
    """Return an immutable representation of ``value`` suitable for storage."""

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
        clock = self.build_clock(profile)
        data_feeds = self.build_data_feeds(profile)
        execution_profile = self.build_execution_profile(profile)
        account_gateway = self.build_account_gateway(profile)
        audit_channel = self.build_audit_channel(profile)
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

    def build_clock(self, profile: ModeProfile) -> MarketClock:
        """Construct the :class:`MarketClock` from the profile payload."""

        timeframe = str(profile.timeframes.get("trigger", ""))
        timezone = str(profile.scheduler.get("timezone", "UTC"))
        return MarketClock(mode=profile.mode, timeframe=timeframe, timezone=timezone)

    def build_data_feeds(self, profile: ModeProfile) -> DataFeedBundle:
        """Construct the :class:`DataFeedBundle` from the ingestion section."""

        ingestion = profile.data_ingestion
        fallbacks = ingestion.get("fallback_providers")
        if isinstance(fallbacks, Sequence) and not isinstance(fallbacks, (str, bytes, bytearray)):
            fallback_tuple = tuple(str(item) for item in fallbacks)
        else:
            fallback_tuple = tuple()

        poll_interval = ingestion.get("poll_interval_sec")
        poll_interval_sec = int(poll_interval) if poll_interval is not None else None

        sla_profile = ingestion.get("sla_threshold_profile")
        sla_threshold_profile = str(sla_profile) if sla_profile is not None else None

        return DataFeedBundle(
            primary=str(ingestion.get("provider", "")),
            fallbacks=fallback_tuple,
            poll_interval_sec=poll_interval_sec,
            catch_up_enabled=bool(ingestion.get("catch_up_enabled", False)),
            manual_fallback_allowed=bool(ingestion.get("manual_fallback_allowed", False)),
            sla_threshold_profile=sla_threshold_profile,
        )

    def build_execution_profile(self, profile: ModeProfile) -> ExecutionProfile:
        """Construct the :class:`ExecutionProfile` for the session."""

        execution_payload = profile.execution
        return ExecutionProfile(
            slippage_bps=execution_payload.get("slippage_bps"),
            latency_simulation_ms=execution_payload.get("latency_simulation_ms"),
            additional_settings=_freeze(
                {
                    key: value
                    for key, value in execution_payload.items()
                    if key not in {"slippage_bps", "latency_simulation_ms"}
                }
            ),
        )

    def build_account_gateway(self, profile: ModeProfile) -> AccountGateway:
        """Construct the :class:`AccountGateway` placeholder for the profile."""

        return AccountGateway(mode=profile.mode, profile_id=profile.profile_id)

    def build_audit_channel(self, profile: ModeProfile) -> AuditChannel:
        """Construct the :class:`AuditChannel` placeholder for the profile."""

        return AuditChannel(profile_id=profile.profile_id, streams=("session", "signals", "execution"))

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


@dataclass(slots=True)
class SessionConfig:
    """Configuration envelope for orchestrating a trading session.

    The structure stores the execution mode and optional snapshot
    recovery hints that will be surfaced to orchestrators. Concrete
    implementations are expected to enrich this payload with
    milestone-specific settings as they come online.
    """

    mode: str
    telemetry_enabled: bool = True
    snapshot_path: Optional[str] = None
    profile_name: Optional[str] = None
    mode_factory: Optional[ModeContextFactory] = None


@dataclass(slots=True)
class SessionContext:
    """Runtime state that is passed into workflows at session start.

    The context object maintains identifiers and feature toggles that
    help downstream pipelines adapt to Backtest, Paper, or Live
    execution environments without leaking implementation details.
    """

    session_id: str
    mode: str
    feature_flags: Optional[dict[str, bool]] = None
    mode_context: Optional[ModeContext] = None


@runtime_checkable
class SessionManager(Protocol):
    """Protocol defining the responsibilities for managing a session.

    Concrete managers coordinate workflow registration, snapshot
    recovery, and health reporting. Implementations should remain pure
    and side-effect free until :meth:`start` is invoked.
    """

    config: SessionConfig
    mode_factory: Optional[ModeContextFactory]

    def start(self, context: SessionContext) -> None:
        """Begin a session with the supplied context."""

    def stop(self) -> None:
        """Stop the session and release any allocated resources."""

    def request_snapshot(self) -> Optional[str]:
        """Return a snapshot identifier if persistence should occur."""


def create_session_context(
    *,
    profile_name: str,
    session_id: str,
    config: SessionConfig | None = None,
    factory: ModeContextFactory | None = None,
    feature_flags: Optional[dict[str, bool]] = None,
) -> SessionContext:
    """Create a :class:`SessionContext` populated with a :class:`ModeContext`.

    The helper wires a :class:`ModeContextFactory` into the lightweight
    session scaffolding so that ``tradectl start --profile ...`` scripts can
    exercise deterministic profile bootstraps during validation runs.
    """

    effective_factory = factory or (config.mode_factory if config else None) or ModeContextFactory()
    mode_context = effective_factory.create(profile_name, session_id=session_id)

    if config is not None:
        if config.profile_name is not None and config.profile_name != profile_name:
            raise ValueError(
                f"SessionConfig.profile_name={config.profile_name!r} does not match requested profile {profile_name!r}"
            )
        if config.mode != mode_context.mode:
            raise ValueError(
                "SessionConfig.mode must align with the profile mode ("
                f"expected {mode_context.mode!r}, found {config.mode!r})"
            )

    return SessionContext(
        session_id=session_id,
        mode=mode_context.mode if config is None else config.mode,
        feature_flags=feature_flags,
        mode_context=mode_context,
    )


@dataclass(slots=True)
class DefaultSessionManager:
    """Concrete :class:`SessionManager` that bridges profiles and workflows."""

    config: SessionConfig
    workflow: "WorkflowOrchestrator"
    mode_factory: ModeContextFactory | None = None
    session_log_dir: Path = field(default_factory=lambda: Path("logs") / "sessions")
    snapshot_root: Path = field(default_factory=lambda: Path("snapshots") / "sessions")
    _active_context: SessionContext | None = field(init=False, default=None)
    _last_result: "WorkflowResult" | None = field(init=False, default=None)
    _session_log_path: Path | None = field(init=False, default=None)
    _snapshot_path: Path | None = field(init=False, default=None)
    _last_plan: tuple[str, ...] = field(init=False, default_factory=tuple)
    _last_workflow_context: "WorkflowContext" | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.session_log_dir = Path(self.session_log_dir)
        self.snapshot_root = Path(self.snapshot_root)
        self.mode_factory = self.mode_factory or self.config.mode_factory or ModeContextFactory()

    @property
    def session_log_path(self) -> Path | None:
        """Return the log path allocated for the active session, if any."""

        return self._session_log_path

    @property
    def snapshot_path(self) -> Path | None:
        """Return the snapshot destination for the active session, if any."""

        return self._snapshot_path

    @property
    def last_result(self) -> "WorkflowResult" | None:
        """Return the most recent :class:`WorkflowResult`, if available."""

        return self._last_result

    @property
    def last_plan(self) -> tuple[str, ...]:
        """Return the most recently materialised workflow plan."""

        return self._last_plan

    @property
    def last_workflow_context(self) -> "WorkflowContext" | None:
        """Return the workflow context from the latest :meth:`start` invocation."""

        return self._last_workflow_context

    def start(self, context: SessionContext) -> None:
        """Initialise the session, wiring a :class:`ModeContext` if required."""

        if self._active_context is not None:
            raise RuntimeError("A session is already running")

        factory = self.mode_factory or ModeContextFactory()
        profile_name = self.config.profile_name or context.mode
        if context.mode_context is None:
            if profile_name is None:
                raise ValueError("A profile name is required to build ModeContext")
            context.mode_context = factory.create(profile_name, session_id=context.session_id)
            context.mode = context.mode_context.mode

        if context.mode != self.config.mode:
            raise ValueError(
                "SessionContext.mode must align with SessionConfig.mode ("
                f"expected {self.config.mode!r}, found {context.mode!r})"
            )

        self.session_log_dir.mkdir(parents=True, exist_ok=True)
        snapshot_dir = self.snapshot_root / context.mode
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        self._session_log_path = self.session_log_dir / f"{context.session_id}.log"
        self._snapshot_path = snapshot_dir / f"{context.session_id}.json"

        plan = tuple(self.workflow.plan())
        self._last_plan = plan

        from .workflow import WorkflowContext  # Imported lazily to avoid circular dependency

        workflow_context = WorkflowContext(session=context, step_sequence=())
        result = self.workflow.run(workflow_context)

        self._active_context = context
        self._last_result = result
        self._last_workflow_context = workflow_context

    def stop(self) -> None:
        """Tear down the active session."""

        self._active_context = None
        self._last_result = None
        self._session_log_path = None
        self._snapshot_path = None
        self._last_workflow_context = None

    def request_snapshot(self) -> Optional[str]:
        """Return the snapshot path allocated during :meth:`start`."""

        if self._active_context is None or self._snapshot_path is None:
            return None
        return str(self._snapshot_path)
