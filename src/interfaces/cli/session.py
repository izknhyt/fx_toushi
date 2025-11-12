"""Session bootstrap utilities for `tradectl start/stop` scaffolding."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.core.session import (
    DefaultSessionManager,
    ModeContext,
    ModeContextFactory,
    SessionConfig,
    create_session_context,
)
from src.core.workflow import PipelineStep, PipelineWorkflow, WorkflowContext

__all__ = ["start_session", "stop_session"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ts(dt: datetime | None = None) -> str:
    value = dt or _utcnow()
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _serialise_mode_context(mode_context: ModeContext) -> Mapping[str, Any]:
    profile = mode_context.profile
    return {
        "mode": mode_context.mode,
        "profile_id": profile.profile_id,
        "schema_version": profile.schema_version,
        "profile_source": str(profile.source),
        "metadata": _normalise(profile.metadata),
        "data_ingestion": _normalise(profile.data_ingestion),
        "timeframes": _normalise(profile.timeframes),
        "risk": _normalise(profile.risk),
        "gates": _normalise(profile.gates),
        "strategies": _normalise(profile.strategies),
        "execution": _normalise(profile.execution),
        "spread": _normalise(profile.spread),
        "funding": _normalise(profile.funding),
        "correlation": _normalise(profile.correlation),
        "scheduler": _normalise(profile.scheduler),
        "clock": {
            "mode": mode_context.clock.mode,
            "timeframe": mode_context.clock.timeframe,
            "timezone": mode_context.clock.timezone,
        },
        "data_feeds": {
            "primary": mode_context.data_feeds.primary,
            "fallbacks": list(mode_context.data_feeds.fallbacks),
            "poll_interval_sec": mode_context.data_feeds.poll_interval_sec,
            "catch_up_enabled": mode_context.data_feeds.catch_up_enabled,
            "manual_fallback_allowed": mode_context.data_feeds.manual_fallback_allowed,
            "sla_threshold_profile": mode_context.data_feeds.sla_threshold_profile,
        },
        "execution_profile": {
            "slippage_bps": mode_context.execution_profile.slippage_bps,
            "latency_simulation_ms": mode_context.execution_profile.latency_simulation_ms,
            "additional_settings": _normalise(mode_context.execution_profile.additional_settings),
        },
        "account_gateway": {
            "mode": mode_context.account_gateway.mode,
            "profile_id": mode_context.account_gateway.profile_id,
        },
        "audit_channel": {
            "profile_id": mode_context.audit_channel.profile_id,
            "streams": list(mode_context.audit_channel.streams),
        },
        "deterministic_seed": mode_context.deterministic_seed,
    }


def _default_session_id(profile: str) -> str:
    suffix = _utcnow().strftime("%Y%m%dT%H%M%SZ")
    return f"{profile}-{suffix}"


def _build_workflow() -> PipelineWorkflow:
    workflow = PipelineWorkflow()

    def _noop(context: WorkflowContext) -> WorkflowContext:
        return context

    workflow.register(PipelineStep(name="bootstrap", handler=_noop))
    return workflow


def _ensure_log_not_exists(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"Session log already exists: {path}")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:  # pragma: no cover - defensive guard
        raise FileNotFoundError(f"Required artifact missing: {path}") from exc


def start_session(
    *,
    profile: str,
    session_id: str | None = None,
    profiles_dir: Path,
    log_dir: Path,
    snapshot_root: Path,
) -> Mapping[str, Any]:
    """Bootstrap a ModeContext and persist evidence artifacts."""

    session_identifier = session_id or _default_session_id(profile)
    workflow = _build_workflow()
    mode_factory = ModeContextFactory(profiles_dir=profiles_dir)
    config = SessionConfig(mode=profile, profile_name=profile, mode_factory=mode_factory)
    manager = DefaultSessionManager(
        config=config,
        workflow=workflow,
        mode_factory=mode_factory,
        session_log_dir=log_dir,
        snapshot_root=snapshot_root,
    )

    session_context = create_session_context(
        profile_name=profile,
        session_id=session_identifier,
        config=config,
        factory=mode_factory,
    )

    manager.start(session_context)

    log_path = manager.session_log_path or (log_dir / f"{session_identifier}.log")
    snapshot_path_str = manager.request_snapshot()
    snapshot_path = (
        Path(snapshot_path_str)
        if snapshot_path_str
        else snapshot_root / session_context.mode / f"{session_identifier}.json"
    )

    log_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    _ensure_log_not_exists(log_path)

    timestamp = _ts()
    mode_context_payload = _serialise_mode_context(session_context.mode_context)
    log_payload: dict[str, Any] = {
        "session": {
            "id": session_identifier,
            "mode": session_context.mode,
            "profile": session_context.mode_context.profile.profile_id,
            "deterministic_seed": session_context.mode_context.deterministic_seed,
            "profile_source": str(session_context.mode_context.profile.source),
            "plan": list(manager.last_plan),
            "log_path": str(log_path),
            "snapshot_path": str(snapshot_path),
        },
        "events": [
            {
                "event": "start",
                "timestamp": timestamp,
                "ctx_mode": session_context.mode,
                "ctx_profile": session_context.mode_context.profile.profile_id,
                "deterministic_seed": session_context.mode_context.deterministic_seed,
            }
        ],
        "mode_context": mode_context_payload,
    }

    log_path.write_text(json.dumps(log_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    snapshot_payload = {
        "session_id": session_identifier,
        "captured_at": timestamp,
        "plan": list(manager.last_plan),
        "mode_context": mode_context_payload,
    }
    snapshot_path.write_text(
        json.dumps(snapshot_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manager.stop()

    return {
        "session_id": session_identifier,
        "profile": profile,
        "mode": session_context.mode,
        "deterministic_seed": session_context.mode_context.deterministic_seed,
        "plan": list(manager.last_plan),
        "log_path": str(log_path),
        "snapshot_path": str(snapshot_path),
        "timestamp": timestamp,
    }


def stop_session(
    *,
    session_id: str,
    log_dir: Path,
    snapshot_root: Path,
) -> Mapping[str, Any]:
    """Append stop evidence to existing session artifacts."""

    log_path = log_dir / f"{session_id}.log"
    log_payload = _load_json(log_path)
    timestamp = _ts()

    events = log_payload.setdefault("events", [])
    if any(event.get("event") == "stop" for event in events):
        raise RuntimeError(f"Session '{session_id}' already stopped")

    session_meta = log_payload.setdefault("session", {})
    mode = session_meta.get("mode")
    snapshot_path = session_meta.get("snapshot_path")
    resolved_snapshot = Path(snapshot_path) if snapshot_path else snapshot_root / str(mode) / f"{session_id}.json"

    events.append(
        {
            "event": "stop",
            "timestamp": timestamp,
        }
    )
    session_meta["stopped_at"] = timestamp
    log_payload["session"] = session_meta
    log_path.write_text(json.dumps(log_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if resolved_snapshot.exists():
        snapshot_payload = _load_json(resolved_snapshot)
    else:
        snapshot_payload = {"session_id": session_id}
    snapshot_payload["stopped_at"] = timestamp
    resolved_snapshot.parent.mkdir(parents=True, exist_ok=True)
    resolved_snapshot.write_text(
        json.dumps(snapshot_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "session_id": session_id,
        "log_path": str(log_path),
        "snapshot_path": str(resolved_snapshot),
        "stopped_at": timestamp,
    }
def _normalise(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalise(val) for key, val in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalise(item) for item in value]
    return value
