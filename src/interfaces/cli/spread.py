"""Implementation for the `tradectl spread` command (see §17.7)."""

from __future__ import annotations

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.calendar import CalendarService
from src.core.gate import GateAggregator, GateState
from src.execution.spread import evaluate_spread_guard
from src.core.spread_guard import (
    DEFAULT_STRATEGY_MANIFEST,
    resolve_news_block_window,
    resolve_spread_thresholds,
)
from src.core.session import ModeContextFactory

logger = logging.getLogger(__name__)

DEFAULT_SPREAD_METRICS = Path("metrics/spread_cooldown.jsonl")
DEFAULT_SPREAD_AUDIT = Path("logs/audit/spread_guard.jsonl")
DEFAULT_GATE_STATE_SNAPSHOT = Path("snapshots/latest/gate_state.json")
DEFAULT_TIME_SYNC_METRICS = Path("metrics/time_sync.jsonl")
DEFAULT_NETWORK_METRICS = Path("metrics/network.jsonl")
DEFAULT_NEWS_BLOCK_WINDOW_MINUTES = (-15, 30)

__all__ = [
    "DEFAULT_GATE_STATE_SNAPSHOT",
    "DEFAULT_SPREAD_AUDIT",
    "DEFAULT_SPREAD_METRICS",
    "inspect",
]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _load_latest_ntp_drift(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return None
    for line in reversed(lines):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        drift = payload.get("clock_drift_ms")
        if drift is None:
            continue
        try:
            return int(round(float(drift)))
        except (TypeError, ValueError):
            continue
    return None


def _resolve_news_event(
    news_event: str | None,
    *,
    window_minutes: tuple[int, int] = DEFAULT_NEWS_BLOCK_WINDOW_MINUTES,
) -> str | None:
    if news_event:
        return news_event
    service = CalendarService()
    now = datetime.now(timezone.utc)
    try:
        if service.is_blocked(now):
            return "calendar_blocked"
    except Exception:  # pragma: no cover - calendar integration is best-effort
        logger.exception("cli.spread.calendar_block_check_failed")
    try:
        events = service.upcoming_events(limit=1)
    except Exception:  # pragma: no cover - calendar integration is best-effort
        logger.exception("cli.spread.calendar_events_failed")
        return None
    if events:
        event = events[0]
        event_ts = event.timestamp
        if event_ts.tzinfo is None:
            event_ts = event_ts.replace(tzinfo=timezone.utc)
        start = now + timedelta(minutes=window_minutes[0])
        end = now + timedelta(minutes=window_minutes[1])
        if start <= event_ts <= end:
            return event.title
    return None


def _update_gate_state(
    *,
    path: Path,
    status: str,
    reason: str | None,
    cooldown_eta: datetime | None,
) -> Path:
    gate_state = GateState.load(path) if path.exists() else GateState()
    aggregator = GateAggregator(initial_state=gate_state)
    aggregator._state.market.spread.state = "halt" if status == "block" else status  # type: ignore[attr-defined]
    aggregator._state.market.spread.reason = reason  # type: ignore[attr-defined]
    aggregator._state.market.spread.cooldown_eta = cooldown_eta  # type: ignore[attr-defined]
    return aggregator.persist_latest(path=path)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _load_last_spread_event(path: Path, *, symbol: str) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return None
    for line in reversed(lines):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("symbol") != symbol:
            continue
        event = payload.get("event")
        if isinstance(event, str) and event.startswith("spread."):
            return payload
    return None


def _record_spread_network_event(
    *,
    path: Path,
    symbol: str,
    status: str,
    cooldown_reason: str | None,
    ntp_drift_ms: int | None,
    news_id: str | None,
    cooldown_eta: datetime | None,
) -> dict[str, object] | None:
    now = datetime.now(timezone.utc)
    last_event = _load_last_spread_event(path, symbol=symbol)
    last_event_name = last_event.get("event") if isinstance(last_event, dict) else None
    last_status = last_event.get("status") if isinstance(last_event, dict) else None
    last_ts = _parse_dt(last_event.get("ts")) if isinstance(last_event, dict) else None

    if status in {"cooldown", "block"}:
        if last_event_name != "spread.cooldown.start" or last_status != status:
            payload = {
                "ts": now.isoformat().replace("+00:00", "Z"),
                "event": "spread.cooldown.start",
                "symbol": symbol,
                "status": status,
                "cooldown_reason": cooldown_reason,
                "ntp_drift_ms": ntp_drift_ms,
                "news_id": news_id,
                "cooldown_eta": cooldown_eta.isoformat() if cooldown_eta else None,
            }
            _append_jsonl(path, payload)
            return payload
        return None

    if last_event_name == "spread.cooldown.start" and last_ts is not None:
        duration_sec = max(0, (now - last_ts).total_seconds())
        payload = {
            "ts": now.isoformat().replace("+00:00", "Z"),
            "event": "spread.cooldown.clear",
            "symbol": symbol,
            "status": status,
            "duration_sec": duration_sec,
            "cooldown_reason": cooldown_reason,
        }
        _append_jsonl(path, payload)
        return payload
    return None


def inspect(
    symbol: str,
    *,
    window: str,
    percentile: int = 95,
    fail_on_gap: bool = False,
    export: str | None = None,
    p95: float | None = None,
    p99: float | None = None,
    ntp_drift_ms: int | None = None,
    news_event: str | None = None,
    cooldown_threshold: float | None = None,
    block_threshold: float | None = None,
    ntp_max_ms: int = 50,
    cooldown_minutes: int | None = None,
    profile: str | None = None,
    strategy_manifest_path: Path = DEFAULT_STRATEGY_MANIFEST,
    metrics_path: Path = DEFAULT_SPREAD_METRICS,
    audit_path: Path = DEFAULT_SPREAD_AUDIT,
    gate_state_path: Path | None = None,
    time_sync_metrics_path: Path = DEFAULT_TIME_SYNC_METRICS,
    network_metrics_path: Path = DEFAULT_NETWORK_METRICS,
) -> dict[str, object]:
    """Inspect spread metrics and emit guardrail signals."""

    if p95 is None or p99 is None:
        raise ValueError("p95 and p99 spread values are required for guardrail evaluation")

    resolved_profile = profile or os.getenv("TRADECTL_PROFILE")
    enable_news_block = True
    news_window = DEFAULT_NEWS_BLOCK_WINDOW_MINUTES
    if resolved_profile:
        try:
            profile_payload = ModeContextFactory().load_profile(resolved_profile)
            thresholds = resolve_spread_thresholds(
                profile_payload, manifest_path=strategy_manifest_path
            )
            if cooldown_threshold is None:
                cooldown_threshold = thresholds["cooldown_threshold"]
            if block_threshold is None:
                block_threshold = thresholds["block_threshold"]
            if cooldown_minutes is None:
                cooldown_minutes = int(thresholds["cooldown_minutes"])
            enable_news_block = bool(profile_payload.gates.get("enable_news_block", True))
            news_window = resolve_news_block_window(strategy_manifest_path)
        except Exception as exc:  # pragma: no cover - config resolution is best-effort
            logger.exception("cli.spread.profile_load_failed", exc_info=exc)

    cooldown_threshold = 1.8 if cooldown_threshold is None else cooldown_threshold
    block_threshold = 2.5 if block_threshold is None else block_threshold
    cooldown_minutes = 5 if cooldown_minutes is None else cooldown_minutes

    if ntp_drift_ms in {None, 0}:
        ntp_drift_ms = _load_latest_ntp_drift(time_sync_metrics_path)
    if enable_news_block or news_event:
        news_event = _resolve_news_event(news_event, window_minutes=news_window)
    else:
        news_event = None

    evaluation = evaluate_spread_guard(
        p95=p95,
        p99=p99,
        cooldown_threshold=cooldown_threshold,
        block_threshold=block_threshold,
        ntp_drift_ms=ntp_drift_ms,
        ntp_max_ms=ntp_max_ms,
        news_event=news_event,
        cooldown_minutes=cooldown_minutes,
    )

    status_label = evaluation.status
    exit_code = 0
    if status_label == "cooldown":
        exit_code = 21
    elif status_label in {"block", "halt"}:
        exit_code = 31

    metrics_payload = {
        "timestamp": _utcnow_iso(),
        "symbol": symbol,
        "window": window,
        "status": status_label,
        "p95": float(evaluation.p95),
        "p99": float(evaluation.p99),
        "cooldown_reason": evaluation.cooldown_reason,
        "ntp_drift_ms": evaluation.ntp_drift_ms,
        "news_id": evaluation.news_id,
        "cooldown_eta": evaluation.expires_at.isoformat() if evaluation.expires_at else None,
        "exit_code": exit_code,
    }
    try:
        _append_jsonl(metrics_path, metrics_payload)
    except OSError as exc:  # pragma: no cover - defensive
        logger.exception("cli.spread.metrics_write_failed", exc_info=exc)

    audit_payload = {
        "ts": _utcnow_iso(),
        "event": "spread_guard.evaluate",
        "symbol": symbol,
        "status": status_label,
        "cooldown_reason": evaluation.cooldown_reason,
        "expires_at": evaluation.expires_at.isoformat() if evaluation.expires_at else None,
    }
    try:
        _append_jsonl(audit_path, audit_payload)
    except OSError as exc:  # pragma: no cover - defensive
        logger.exception("cli.spread.audit_write_failed", exc_info=exc)

    network_event = _record_spread_network_event(
        path=network_metrics_path,
        symbol=symbol,
        status=status_label,
        cooldown_reason=evaluation.cooldown_reason,
        ntp_drift_ms=evaluation.ntp_drift_ms,
        news_id=evaluation.news_id,
        cooldown_eta=evaluation.expires_at,
    )

    gate_state_snapshot: str | None = None
    if gate_state_path is not None:
        gate_state_snapshot = str(
            _update_gate_state(
                path=gate_state_path,
                status=status_label,
                reason=evaluation.cooldown_reason,
                cooldown_eta=evaluation.expires_at,
            )
        )

    payload: dict[str, object] = {
        "symbol": symbol,
        "window": window,
        "status": status_label,
        "cooldown_reason": evaluation.cooldown_reason,
        "p95": float(evaluation.p95),
        "p99": float(evaluation.p99),
        "ntp_drift_ms": evaluation.ntp_drift_ms,
        "news_id": evaluation.news_id,
        "exit_code": exit_code,
        "metrics_path": str(metrics_path),
        "audit_path": str(audit_path),
        "network_metrics_path": str(network_metrics_path),
        "fail_on_gap": fail_on_gap,
        "percentile": percentile,
    }
    if status_label == "block":
        payload["kill_switch_recommendation"] = "soft_stop"
    if evaluation.expires_at:
        payload["cooldown_eta"] = evaluation.expires_at.isoformat()
    if gate_state_snapshot:
        payload["gate_state_path"] = gate_state_snapshot
    if network_event:
        payload["network_event"] = network_event

    if export:
        Path(export).parent.mkdir(parents=True, exist_ok=True)
        Path(export).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "cli.spread.inspect",
        extra={
            "symbol": symbol,
            "window": window,
            "status": status_label,
            "exit_code": exit_code,
            "cooldown_reason": evaluation.cooldown_reason,
        },
    )
    return payload
