"""Implementation for the `tradectl spread` command (see §17.7)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.core.gate import GateAggregator, GateState
from src.execution.spread import evaluate_spread_guard

logger = logging.getLogger(__name__)

DEFAULT_SPREAD_METRICS = Path("metrics/spread_cooldown.jsonl")
DEFAULT_SPREAD_AUDIT = Path("logs/audit/spread_guard.jsonl")
DEFAULT_GATE_STATE_SNAPSHOT = Path("snapshots/latest/gate_state.json")

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
    cooldown_threshold: float = 1.8,
    block_threshold: float = 2.5,
    ntp_max_ms: int = 50,
    cooldown_minutes: int = 5,
    metrics_path: Path = DEFAULT_SPREAD_METRICS,
    audit_path: Path = DEFAULT_SPREAD_AUDIT,
    gate_state_path: Path | None = None,
) -> dict[str, object]:
    """Inspect spread metrics and emit guardrail signals."""

    if p95 is None or p99 is None:
        raise ValueError("p95 and p99 spread values are required for guardrail evaluation")

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
        "fail_on_gap": fail_on_gap,
        "percentile": percentile,
    }
    if evaluation.expires_at:
        payload["cooldown_eta"] = evaluation.expires_at.isoformat()
    if gate_state_snapshot:
        payload["gate_state_path"] = gate_state_snapshot

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
