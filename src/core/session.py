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

import contextlib
import hashlib
import json
import os
import time
import uuid
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Protocol,
    runtime_checkable,
)

from yaml import safe_load

from src.data.service import IngestionMetricsCollector
from src.core.health import HealthMonitor

if TYPE_CHECKING:  # pragma: no cover - import cycle guard for type checking only
    from .workflow import WorkflowContext, WorkflowOrchestrator, WorkflowResult

__all__ = [
    "AccountGateway",
    "AuditChannel",
    "DataFeedBundle",
    "ExecutionProfile",
    "HitlProfile",
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

_DEFAULT_HASH = "sha256:" + ("0" * 64)
_DEFAULT_RESYNC_JOBS_PATH = Path("metrics/resync_jobs.jsonl")
_DEFAULT_RESYNC_QUEUE_PATH = Path("metrics/resync_queue.jsonl")
_DEFAULT_RESYNC_LATENCY_PATH = Path("metrics/resync_latency.jsonl")
_MAJOR_SYMBOLS = {"USDJPY", "EURUSD", "GBPUSD", "AUDUSD"}
_DEFAULT_HEALTH_STATE_PATH = Path("snapshots/latest/health_state.json")

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


def _timeframe_to_seconds(value: str | None) -> int | None:
    if not value:
        return None
    token = value.strip().lower()
    if not token:
        return None
    if token.endswith("m") and token[:-1].isdigit():
        return int(token[:-1]) * 60
    if token.endswith("h") and token[:-1].isdigit():
        return int(token[:-1]) * 3600
    if token.startswith("m") and token[1:].isdigit():
        return int(token[1:]) * 60
    if token.startswith("h") and token[1:].isdigit():
        return int(token[1:]) * 3600
    if token.isdigit():
        return int(token)
    return None


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
    def from_mapping(cls, payload: Mapping[str, Any], *, source: Path) -> ModeProfile:
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
class HitlProfile:
    """Normalized HITL settings shared across modes."""

    board_mode_default: str
    enable_news_block: bool
    require_double_ack_on_resume: bool
    enforce_research_ticket: bool
    required_roles: tuple[str, ...]
    manual_comment_required: bool
    comment_min_length: int
    comment_max_length: int


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
    hitl: HitlProfile
    catch_up_state: str = "idle"


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
        hitl_profile = self.build_hitl_profile(profile)
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
            hitl=hitl_profile,
        )

    def load_profile(self, profile_name: str) -> ModeProfile:
        """Return a cached :class:`ModeProfile` for ``profile_name``."""

        return _load_profile_cached(self._profiles_dir, profile_name)

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
            fallback_tuple = ()

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

        return AuditChannel(
            profile_id=profile.profile_id, streams=("session", "signals", "execution")
        )

    def build_hitl_profile(self, profile: ModeProfile) -> HitlProfile:
        """Normalize HITL gate settings for consistent cross-mode behavior."""

        gates = profile.gates
        required_roles = gates.get("required_roles") or ()
        if isinstance(required_roles, Sequence) and not isinstance(
            required_roles, (str, bytes, bytearray)
        ):
            roles = tuple(str(role) for role in required_roles)
        else:
            roles = ()
        return HitlProfile(
            board_mode_default=str(gates.get("board_mode_default", "normal")),
            enable_news_block=bool(gates.get("enable_news_block", False)),
            require_double_ack_on_resume=bool(gates.get("require_double_ack_on_resume", False)),
            enforce_research_ticket=bool(gates.get("enforce_research_ticket", False)),
            required_roles=roles,
            manual_comment_required=bool(gates.get("manual_comment_required", False)),
            comment_min_length=int(gates.get("comment_min_length", 0) or 0),
            comment_max_length=int(gates.get("comment_max_length", 0) or 0),
        )

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
    snapshot_path: str | None = None
    profile_name: str | None = None
    mode_factory: ModeContextFactory | None = None


@dataclass(slots=True)
class SessionContext:
    """Runtime state that is passed into workflows at session start.

    The context object maintains identifiers and feature toggles that
    help downstream pipelines adapt to Backtest, Paper, or Live
    execution environments without leaking implementation details.
    """

    session_id: str
    mode: str
    feature_flags: dict[str, bool] | None = None
    mode_context: ModeContext | None = None


@runtime_checkable
class SessionManager(Protocol):
    """Protocol defining the responsibilities for managing a session.

    Concrete managers coordinate workflow registration, snapshot
    recovery, and health reporting. Implementations should remain pure
    and side-effect free until :meth:`start` is invoked.
    """

    config: SessionConfig
    mode_factory: ModeContextFactory | None

    def start(self, context: SessionContext) -> None:
        """Begin a session with the supplied context."""

    def stop(self) -> None:
        """Stop the session and release any allocated resources."""

    def request_snapshot(self) -> str | None:
        """Return a snapshot identifier if persistence should occur."""

    def catch_up(
        self,
        *,
        since: str | None = None,
        symbols: Sequence[str] | None = None,
        force: bool = False,
        failover_report: bool = False,
        dry_run: bool = False,
        attachments: Sequence[str] | None = None,
    ) -> Mapping[str, Any] | None:
        """Replay missing market data windows and summarise the resync."""


def create_session_context(
    *,
    profile_name: str,
    session_id: str,
    config: SessionConfig | None = None,
    factory: ModeContextFactory | None = None,
    feature_flags: dict[str, bool] | None = None,
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
                "SessionConfig.profile_name="
                f"{config.profile_name!r} does not match requested profile {profile_name!r}"
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


@lru_cache(maxsize=16)
def _load_profile_cached(profiles_dir: Path, profile_name: str) -> ModeProfile:
    path = profiles_dir / f"{profile_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Profile configuration not found: {path}")
    payload = safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Profile YAML at {path} must contain a mapping root")
    return ModeProfile.from_mapping(payload, source=path)


@dataclass(slots=True)
class DefaultSessionManager:
    """Concrete :class:`SessionManager` that bridges profiles and workflows."""

    config: SessionConfig
    workflow: WorkflowOrchestrator
    mode_factory: ModeContextFactory | None = None
    session_log_dir: Path = field(default_factory=lambda: Path("logs") / "sessions")
    snapshot_root: Path = field(default_factory=lambda: Path("snapshots") / "sessions")
    _active_context: SessionContext | None = field(init=False, default=None)
    _last_result: WorkflowResult | None = field(init=False, default=None)
    _session_log_path: Path | None = field(init=False, default=None)
    _snapshot_path: Path | None = field(init=False, default=None)
    _last_plan: tuple[str, ...] = field(init=False, default_factory=tuple)
    _last_workflow_context: WorkflowContext | None = field(init=False, default=None)

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
    def last_result(self) -> WorkflowResult | None:
        """Return the most recent :class:`WorkflowResult`, if available."""

        return self._last_result

    @property
    def last_plan(self) -> tuple[str, ...]:
        """Return the most recently materialised workflow plan."""

        return self._last_plan

    @property
    def last_workflow_context(self) -> WorkflowContext | None:
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

        workflow_context = WorkflowContext(
            session=context,
            step_sequence=(),
            planned_steps=plan,
        )
        result = self.workflow.run(workflow_context)

        self._active_context = context
        self._last_result = result
        self._last_workflow_context = workflow_context
        cfg_hash = os.getenv("TRADECTL_CFG_HASH") or _DEFAULT_HASH
        data_hash = os.getenv("TRADECTL_DATA_HASH") or _DEFAULT_HASH
        self._check_snapshot_consistency(cfg_hash=cfg_hash, data_hash=data_hash)

    def stop(self) -> None:
        """Tear down the active session."""

        self._active_context = None
        self._last_result = None
        self._session_log_path = None
        self._snapshot_path = None
        self._last_workflow_context = None

    def request_snapshot(self) -> str | None:
        """Return the snapshot path allocated during :meth:`start`."""

        if self._active_context is None or self._snapshot_path is None:
            return None
        return str(self._snapshot_path)

    def catch_up(
        self,
        *,
        since: str | None = None,
        symbols: Sequence[str] | None = None,
        force: bool = False,
        failover_report: bool = False,
        dry_run: bool = False,
        attachments: Sequence[str] | None = None,
        metrics_collector: IngestionMetricsCollector | None = None,
        timeframe: str | None = None,
        provider_priority: Sequence[str] | None = None,
        provider_handlers: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any] | None:
        """Resynchronise historical data and return a deterministic summary.

        Expected keys for the summary (see detailed design §89):
        - catch_up_elapsed_sec: int
        - catch_up_lag_minutes: int
        - recovered_symbols: list[str]
        - failover_used: list[str]
        - manual_csv_required: bool
        - cfg_hash: str (sha256:...)
        - data_hash: str (sha256:...)
        - board_mode: str (normal|guarded|halted)
        - mode: str (backtest|paper|live)
        """

        start = time.perf_counter()
        now = datetime.now(timezone.utc)
        if not dry_run and self._active_context and self._active_context.mode_context:
            self._active_context.mode_context = replace(
                self._active_context.mode_context,
                catch_up_state="resyncing",
            )
        resync_job_id = str(uuid.uuid4())
        parsed_since = self._parse_since(since)
        range_minutes = self._compute_range_minutes(parsed_since, now)
        timeframe_seconds = _timeframe_to_seconds(timeframe or "M5")
        effective_mode = self.config.mode
        cfg_hash = os.getenv("TRADECTL_CFG_HASH") or _DEFAULT_HASH
        data_hash = os.getenv("TRADECTL_DATA_HASH") or _DEFAULT_HASH
        board_mode = os.getenv("TRADECTL_BOARD_MODE") or "normal"
        determinism_hash = (
            os.getenv("TRADECTL_DETERMINISM_HASH") or self._load_latest_determinism_hash()
        )
        gate_state = self._load_gate_state()
        if gate_state:
            cfg_hash = gate_state.get("cfg_hash", cfg_hash) or cfg_hash
            data_hash = gate_state.get("data_hash", data_hash) or data_hash
            board_mode = gate_state.get("board_mode", board_mode) or board_mode
        failover_env = os.getenv("TRADECTL_RESYNC_FAILOVER_USED", "")
        failover_used = (
            [token for token in failover_env.split(",") if token.strip()] if failover_env else []
        )
        measured = self._load_latest_resync_stats()
        collector_snapshot = metrics_collector.snapshot() if metrics_collector else {}

        def _coalesce_int(*values: Any, default: int = 0) -> int:
            for val in values:
                if val is None:
                    continue
                try:
                    return int(val)
                except (TypeError, ValueError):
                    continue
            return default

        def _coalesce_float(*values: Any, default: float = 0.0) -> float:
            for val in values:
                if val is None:
                    continue
                try:
                    return float(val)
                except (TypeError, ValueError):
                    continue
            return default

        cfg_hash = measured.get("cfg_hash") or cfg_hash
        data_hash = measured.get("data_hash") or data_hash
        board_mode = measured.get("board_mode") or board_mode
        effective_mode = measured.get("mode") or effective_mode
        determinism_hash = measured.get("determinism_hash") or determinism_hash

        catch_up_elapsed_sec = _coalesce_int(
            measured.get("catch_up_elapsed_sec"),
            int(time.perf_counter() - start),
            default=0,
        )
        catch_up_lag_minutes = _coalesce_int(
            measured.get("catch_up_lag_minutes"),
            collector_snapshot.get("catch_up_lag_minutes"),
            os.getenv("TRADECTL_RESYNC_LAG_MINUTES"),
            default=0,
        )
        failover_used = list(measured.get("failover_used") or failover_used)
        manual_csv_required = bool(measured.get("manual_csv_required", False))
        recovered_symbols = list(measured.get("recovered_symbols") or (symbols or ()))
        ingestion_metrics = self._load_latest_ingestion_metrics()
        fetch_p95_ms = _coalesce_float(
            collector_snapshot.get("fetch_p95_ms"),
            measured.get("fetch_p95_ms"),
            ingestion_metrics.get("fetch_p95_ms"),
            os.getenv("TRADECTL_RESYNC_FETCH_P95_MS"),
            default=500.0,
        )
        fetch_p99_ms = _coalesce_float(
            collector_snapshot.get("fetch_p99_ms"),
            measured.get("fetch_p99_ms"),
            ingestion_metrics.get("fetch_p99_ms"),
            os.getenv("TRADECTL_RESYNC_FETCH_P99_MS"),
            default=800.0,
        )
        retry_count = _coalesce_int(
            collector_snapshot.get("retry_count"),
            measured.get("retry_count"),
            ingestion_metrics.get("retry_count"),
            os.getenv("TRADECTL_RESYNC_RETRY_COUNT"),
            default=0,
        )
        quality_flag = _coalesce_int(
            measured.get("quality_flag"),
            ingestion_metrics.get("quality_flag"),
            os.getenv("TRADECTL_RESYNC_QUALITY_FLAG"),
            default=0,
        )
        latency_status = (
            collector_snapshot.get("latency_status")
            or measured.get("latency_status")
            or ingestion_metrics.get("latency_status")
            or os.getenv("TRADECTL_RESYNC_LATENCY_STATUS", "ok")
        )
        if (
            not measured.get("catch_up_lag_minutes")
            and ingestion_metrics.get("catch_up_lag_minutes") is not None
        ):
            catch_up_lag_minutes = int(ingestion_metrics["catch_up_lag_minutes"])
        if (
            range_minutes is not None
            and not measured.get("catch_up_lag_minutes")
            and ingestion_metrics.get("catch_up_lag_minutes") is None
            and catch_up_lag_minutes == 0
        ):
            catch_up_lag_minutes = range_minutes
        resync_latency_sec = None
        resync_latency_ratio = None
        if parsed_since is not None:
            resync_latency_sec = int((now - parsed_since).total_seconds())
            if timeframe_seconds:
                resync_latency_ratio = resync_latency_sec / float(timeframe_seconds)
        if range_minutes is None and catch_up_lag_minutes > 0:
            range_minutes = catch_up_lag_minutes
        priority = self._compute_catch_up_priority(catch_up_lag_minutes, symbols or ())
        failover_plan = list(provider_priority or ())
        if priority == "critical" and not failover_plan:
            failover_plan = ["cache", "dukascopy", "yfinance"]
        if retry_count >= 3 and not manual_csv_required:
            manual_csv_required = True
        job_start = parsed_since
        if job_start is None and catch_up_lag_minutes > 0:
            job_start = now - timedelta(minutes=catch_up_lag_minutes)
        backfill_jobs, queue_path = self._enqueue_backfill_jobs(
            resync_job_id=resync_job_id,
            start=job_start,
            end=now,
            symbols=list(symbols or ()),
            timeframe=timeframe or "M5",
            priority=priority,
            failover_plan=failover_plan,
            manual_csv_required=manual_csv_required,
            retry_count=retry_count,
            dry_run=dry_run,
        )
        resync_processing: Mapping[str, Any] | None = None
        if backfill_jobs and not dry_run:
            try:
                from src.core.resync import ResyncCoordinator
                from src.data.quality import DataQualityGuard

                tf_label = (timeframe or "M5").strip().lower()
                expected_minutes = 5
                if tf_label.endswith("m") and tf_label[:-1].isdigit():
                    expected_minutes = int(tf_label[:-1])
                elif tf_label.endswith("h") and tf_label[:-1].isdigit():
                    expected_minutes = int(tf_label[:-1]) * 60
                elif tf_label.startswith("m") and tf_label[1:].isdigit():
                    expected_minutes = int(tf_label[1:])
                elif tf_label.startswith("h") and tf_label[1:].isdigit():
                    expected_minutes = int(tf_label[1:]) * 60
                quality_guard = DataQualityGuard(
                    expected_timeframe_minutes=expected_minutes,
                    max_gap_minutes=max(expected_minutes * 2, 10),
                )
                coordinator = ResyncCoordinator(queue_path=queue_path or _DEFAULT_RESYNC_QUEUE_PATH)
                resync_processing = coordinator.process_jobs(
                    jobs=backfill_jobs,
                    provider_handlers=provider_handlers,
                    provider_sla_thresholds=None,
                    data_quality_guard=quality_guard,
                    metrics_path=Path(
                        os.getenv(
                            "TRADECTL_INGESTION_METRICS_PATH",
                            "metrics/data_ingestion_sla.jsonl",
                        )
                    ),
                )
            except Exception:
                resync_processing = None
        if resync_processing:
            failover_used = list(
                dict.fromkeys(failover_used + list(resync_processing.get("failover_used") or ()))
            )
            retry_count = max(retry_count, int(resync_processing.get("retry_count") or 0))
            manual_csv_required = manual_csv_required or bool(
                resync_processing.get("manual_csv_enqueued")
            )
            backfill_jobs = list(resync_processing.get("jobs") or backfill_jobs)
        if metrics_collector and not dry_run and provider_handlers is not None:
            try:
                from src.data.rate_limit_guard import RateLimitGuard
                from src.data.service import fetch_latest

                worker_plan_enabled = os.getenv("TRADECTL_WORKER_PLAN_ENABLED", "1") != "0"
                guard_enabled = os.getenv("TRADECTL_RATE_LIMIT_GUARD_ENABLED", "1") != "0"
                stages_env = os.getenv("TRADECTL_RATE_LIMIT_STAGES", "stage0,stage1,stage2")
                stages = [stage.strip() for stage in stages_env.split(",") if stage.strip()] or [
                    "stage0"
                ]
                rate_limit_guard = None
                if guard_enabled:
                    rate_limit_guard = RateLimitGuard(
                        tokens_per_minute=_coalesce_float(
                            os.getenv("TRADECTL_RATE_LIMIT_TPM"), default=60.0
                        ),
                        burst_tokens=_coalesce_float(
                            os.getenv("TRADECTL_RATE_LIMIT_BURST"), default=90.0
                        ),
                        poll_interval_sec=_coalesce_float(
                            os.getenv("TRADECTL_RATE_LIMIT_POLL_SEC"), default=15.0
                        ),
                        stages=stages,
                    )
                rate_limit_log_path = Path(
                    os.getenv("TRADECTL_RATE_LIMIT_LOG", "metrics/rate_limit_window.jsonl")
                )

                _ = fetch_latest(
                    symbols=list(symbols or ()),
                    timeframe=timeframe or "M5",
                    provider_priority=provider_priority or ("primary",),
                    provider_handlers=dict(provider_handlers),
                    metrics_collector=metrics_collector,
                    rate_limit_guard=rate_limit_guard,
                    rate_limit_state={},
                    rate_limit_log_path=rate_limit_log_path,
                    apply_worker_plan=worker_plan_enabled,
                )
            except Exception:
                pass
        if not measured.get("catch_up_elapsed_sec"):
            catch_up_elapsed_sec = max(0, int(time.perf_counter() - start))
        result = {
            "catch_up_elapsed_sec": max(0, catch_up_elapsed_sec),
            "catch_up_lag_minutes": catch_up_lag_minutes,
            "recovered_symbols": recovered_symbols,
            "failover_used": failover_used,
            "manual_csv_required": manual_csv_required,
            "cfg_hash": cfg_hash,
            "data_hash": data_hash,
            "board_mode": board_mode,
            "mode": effective_mode,
            "determinism_hash": determinism_hash,
            "attachments": list(attachments or ()),
            "since": since,
            "force": force,
            "failover_report": failover_report,
            "dry_run": dry_run,
            "fetch_p95_ms": fetch_p95_ms,
            "fetch_p99_ms": fetch_p99_ms,
            "retry_count": retry_count,
            "latency_status": latency_status,
            "quality_flag": quality_flag,
            "resync_job_id": resync_job_id,
            "range_minutes": range_minutes,
            "priority": priority,
            "failover_plan": failover_plan,
            "resync_latency_sec": resync_latency_sec,
            "resync_latency_ratio": resync_latency_ratio,
            "backfill_jobs": backfill_jobs,
            "resync_queue_path": str(queue_path) if queue_path else None,
        }
        if not dry_run:
            self._update_session_snapshot(resync_summary=result)
            self._apply_catch_up_thresholds(resync_summary=result)
        self._log_resync_job(
            job_id=resync_job_id,
            range_minutes=range_minutes,
            symbols=list(symbols or ()),
            priority=priority,
            failover_plan=failover_plan,
            manual_csv_required=manual_csv_required,
            duration_sec=catch_up_elapsed_sec,
            status="dry_run" if dry_run else "completed",
        )
        if resync_latency_sec is not None:
            self._log_resync_latency(
                resync_job_id=resync_job_id,
                resync_latency_sec=resync_latency_sec,
                resync_latency_ratio=resync_latency_ratio,
                timeframe=timeframe or "M5",
            )
        if metrics_collector:
            metrics_path = Path(
                os.getenv("TRADECTL_INGESTION_METRICS_PATH", "metrics/data_ingestion_sla.jsonl")
            )
            with contextlib.suppress(Exception):  # pragma: no cover - defensive
                metrics_collector.write_snapshot(metrics_path=metrics_path)
        if self._active_context and self._active_context.mode_context:
            self._active_context.mode_context = replace(
                self._active_context.mode_context,
                catch_up_state="idle",
            )
        self._check_snapshot_consistency(cfg_hash=cfg_hash, data_hash=data_hash)
        return result

    def _check_snapshot_consistency(self, *, cfg_hash: str, data_hash: str) -> None:
        gate_state = self._load_gate_state()
        if not gate_state:
            return
        mismatch = []
        if gate_state.get("cfg_hash") and gate_state.get("cfg_hash") != cfg_hash:
            mismatch.append("cfg_hash")
        if gate_state.get("data_hash") and gate_state.get("data_hash") != data_hash:
            mismatch.append("data_hash")
        if mismatch:
            HealthMonitor().raise_condition(
                "warning",
                "snapshot_consistency_mismatch",
                detail=f"mismatch={','.join(mismatch)}",
                recommended_action="verify_snapshot_consistency",
            )

    def _update_session_snapshot(self, *, resync_summary: Mapping[str, Any]) -> None:
        if self._snapshot_path is None:
            return
        snapshot_path = Path(self._snapshot_path)
        payload: dict[str, Any] = {}
        if snapshot_path.exists():
            try:
                payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
        payload.setdefault(
            "session_id", self._active_context.session_id if self._active_context else None
        )
        payload["updated_at"] = (
            datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
        payload["catch_up_summary"] = dict(resync_summary)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _apply_catch_up_thresholds(self, *, resync_summary: Mapping[str, Any]) -> None:
        lag = resync_summary.get("catch_up_lag_minutes")
        try:
            lag_minutes = int(lag) if lag is not None else None
        except (TypeError, ValueError):
            lag_minutes = None
        if lag_minutes is None:
            return
        monitor = HealthMonitor()
        reason = "data_latency_catch_up"
        if lag_minutes >= 30:
            monitor.raise_condition(
                "critical",
                reason,
                detail=f"catch_up_lag_minutes={lag_minutes}",
                recommended_action="runbook:RUN-DATA-06#guarded_checklist",
            )
            monitor.suggest_guarded(
                reason=reason,
                runbook="docs/runbooks/RUN-DATA-06.md",
                evidence=[str(self._snapshot_path or "")],
            )
        elif lag_minutes >= 20:
            monitor.raise_condition(
                "warning",
                reason,
                detail=f"catch_up_lag_minutes={lag_minutes}",
                recommended_action="runbook:RUN-DATA-06#notify_ops",
            )
        else:
            monitor.suggest_resume(
                reason="data_latency_catch_up_recovered",
                runbook="docs/runbooks/RUN-DATA-05.md",
                evidence=[str(self._snapshot_path or "")],
            )
        snapshot = monitor.snapshot().to_dict()
        _DEFAULT_HEALTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _DEFAULT_HEALTH_STATE_PATH.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _load_gate_state(self) -> Mapping[str, Any]:
        """Best-effort load of the latest gate state for hashes/board mode."""

        path = Path(os.getenv("TRADECTL_GATE_STATE_PATH", "snapshots/latest/gate_state.json"))
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        cfg_hash = data.get("cfg_hash") or os.getenv("TRADECTL_CFG_HASH") or _DEFAULT_HASH
        data_hash = data.get("data_hash") or os.getenv("TRADECTL_DATA_HASH") or _DEFAULT_HASH
        board_mode = "guarded"
        if data.get("auto_execute") is True:
            board_mode = "normal"
        return {"cfg_hash": cfg_hash, "data_hash": data_hash, "board_mode": board_mode}

    def _load_latest_determinism_hash(self) -> str | None:
        """Return the latest determinism hash from registry log if present."""

        log_path = Path(os.getenv("TRADECTL_DETERMINISM_LOG", "logs/strategy/registry.log"))
        if not log_path.exists():
            return None
        try:
            with log_path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                end = handle.tell()
                handle.seek(max(0, end - 8192))
                data = handle.read().decode("utf-8", errors="ignore")
            lines = [line for line in data.splitlines() if line.strip()]
            if not lines:
                return None
            last = json.loads(lines[-1])
            return last.get("determinism_hash") or last.get("deterministic_hash")
        except Exception:
            return None

    def _load_latest_resync_stats(self) -> Mapping[str, Any]:
        """Best-effort parse of the latest resync events for SLA metrics."""

        path = Path(os.getenv("TRADECTL_RESYNC_LOG_PATH", "logs/resync/resync_events.jsonl"))
        if not path.exists():
            return {}
        try:
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception:
            return {}

        for raw in reversed(lines):
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            event_name = record.get("event")
            if event_name not in {"resync.completed", "resync.simulated"}:
                continue
            payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
            stats: dict[str, Any] = {}
            stats.update(payload)
            for key in (
                "catch_up_elapsed_sec",
                "catch_up_lag_minutes",
                "recovered_symbols",
                "failover_used",
                "manual_csv_required",
                "cfg_hash",
                "data_hash",
                "fetch_p95_ms",
                "fetch_p99_ms",
                "retry_count",
                "latency_status",
                "determinism_hash",
            ):
                if key in record and key not in stats:
                    stats[key] = record[key]
            context = record.get("context") or {}
            if isinstance(context, dict):
                for ctx_key, dest_key in (
                    ("mode", "mode"),
                    ("board_mode", "board_mode"),
                    ("cfg_hash", "cfg_hash"),
                    ("data_hash", "data_hash"),
                ):
                    if ctx_key in context and dest_key not in stats:
                        stats[dest_key] = context[ctx_key]
            if "symbols" in record and "recovered_symbols" not in stats:
                stats["recovered_symbols"] = record.get("symbols")
            if "since" in record and "since" not in stats:
                stats["since"] = record.get("since")
            return stats
        return {}

    def _load_latest_ingestion_metrics(self) -> Mapping[str, Any]:
        """Return latest ingestion SLA metrics for fetch latency."""

        path = Path(
            os.getenv("TRADECTL_INGESTION_METRICS_PATH", "metrics/data_ingestion_sla.jsonl")
        )
        if not path.exists():
            return {}
        try:
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception:
            return {}
        for raw in reversed(lines):
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            if record.get("phase") not in {None, "fetch"}:
                continue
            payload: dict[str, Any] = {}
            if "p95_latency_sec" in record:
                with contextlib.suppress(TypeError, ValueError):
                    payload["fetch_p95_ms"] = float(record["p95_latency_sec"]) * 1000
            if "p99_latency_sec" in record:
                with contextlib.suppress(TypeError, ValueError):
                    payload["fetch_p99_ms"] = float(record["p99_latency_sec"]) * 1000
            if "latency_status" in record or "status" in record:
                payload["latency_status"] = record.get("latency_status") or record.get("status")
            if "retry_count" in record:
                with contextlib.suppress(TypeError, ValueError):
                    payload["retry_count"] = int(record["retry_count"])
            if "catch_up_lag_minutes" in record:
                payload["catch_up_lag_minutes"] = record.get("catch_up_lag_minutes")
            if "quality_flag" in record:
                with contextlib.suppress(TypeError, ValueError):
                    payload["quality_flag"] = int(record["quality_flag"])
            if payload:
                return payload
        return {}

    @staticmethod
    def _parse_since(value: str | None) -> datetime | None:
        if not value:
            return None
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _compute_range_minutes(since: datetime | None, now: datetime) -> int | None:
        if since is None:
            return None
        delta = now - since
        minutes = int(delta.total_seconds() // 60)
        return max(minutes, 0)

    @staticmethod
    def _compute_catch_up_priority(lag_minutes: int, symbols: Sequence[str]) -> str:
        majors = sum(1 for symbol in symbols if symbol.upper() in _MAJOR_SYMBOLS)
        if lag_minutes >= 30 and majors >= 4:
            return "critical"
        if lag_minutes >= 30:
            return "high"
        if lag_minutes >= 20:
            return "high"
        return "normal"

    def _log_resync_job(
        self,
        *,
        job_id: str,
        range_minutes: int | None,
        symbols: Sequence[str],
        priority: str,
        failover_plan: Sequence[str],
        manual_csv_required: bool,
        duration_sec: int,
        status: str,
    ) -> None:
        path = Path(os.getenv("TRADECTL_RESYNC_JOBS_PATH", str(_DEFAULT_RESYNC_JOBS_PATH)))
        payload = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "job_id": job_id,
            "range_minutes": range_minutes,
            "symbols": list(symbols),
            "priority": priority,
            "failover_plan": list(failover_plan),
            "manual_csv_required": bool(manual_csv_required),
            "duration_sec": int(duration_sec),
            "status": status,
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")
        except OSError:
            return

    def _log_resync_latency(
        self,
        *,
        resync_job_id: str,
        resync_latency_sec: int,
        resync_latency_ratio: float | None,
        timeframe: str,
    ) -> None:
        path = Path(os.getenv("TRADECTL_RESYNC_LATENCY_PATH", str(_DEFAULT_RESYNC_LATENCY_PATH)))
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "resync_job_id": resync_job_id,
            "resync_latency_sec": int(resync_latency_sec),
            "timeframe": timeframe,
        }
        if resync_latency_ratio is not None:
            payload["resync_latency_ratio"] = float(resync_latency_ratio)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")
        except OSError:
            return

    @staticmethod
    def _resolve_resync_queue_path() -> Path:
        path = os.getenv("TRADECTL_RESYNC_QUEUE_PATH")
        return Path(path) if path else _DEFAULT_RESYNC_QUEUE_PATH

    def _enqueue_backfill_jobs(
        self,
        *,
        resync_job_id: str,
        start: datetime | None,
        end: datetime,
        symbols: Sequence[str],
        timeframe: str,
        priority: str,
        failover_plan: Sequence[str],
        manual_csv_required: bool,
        retry_count: int,
        dry_run: bool,
    ) -> tuple[list[Mapping[str, Any]], Path | None]:
        if not symbols or start is None:
            return [], None
        total_minutes = int((end - start).total_seconds() // 60)
        if total_minutes <= 0:
            return [], None
        split_window = (
            manual_csv_required and retry_count >= 3 and total_minutes >= 24 * 60
        )
        segment_minutes = 4 * 60 if split_window else total_minutes
        segments: list[tuple[datetime, datetime]] = []
        cursor = start
        while cursor < end:
            segment_end = min(end, cursor + timedelta(minutes=segment_minutes))
            if segment_end <= cursor:
                break
            segments.append((cursor, segment_end))
            cursor = segment_end
        queue_path = self._resolve_resync_queue_path()
        status = "planned" if dry_run else "queued"
        payloads: list[Mapping[str, Any]] = []
        for idx, (seg_start, seg_end) in enumerate(segments, start=1):
            range_minutes = int((seg_end - seg_start).total_seconds() // 60)
            payloads.append(
                {
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "job_id": str(uuid.uuid4()),
                    "resync_job_id": resync_job_id,
                    "segment_index": idx,
                    "segment_total": len(segments),
                    "start": seg_start.replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "end": seg_end.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "range_minutes": range_minutes,
                    "symbols": list(symbols),
                    "timeframe": timeframe,
                    "priority": priority,
                    "failover_plan": list(failover_plan),
                    "manual_csv_required": bool(manual_csv_required),
                    "retry_count": int(retry_count),
                    "status": status,
                }
            )
        if payloads:
            try:
                queue_path.parent.mkdir(parents=True, exist_ok=True)
                with queue_path.open("a", encoding="utf-8") as handle:
                    for payload in payloads:
                        handle.write(json.dumps(payload, ensure_ascii=False))
                        handle.write("\n")
            except OSError:
                return payloads, None
        return payloads, queue_path if payloads else None
