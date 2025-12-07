"""Kill switch commands for guardrail operations."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping

logger = logging.getLogger(__name__)

DEFAULT_KILL_SWITCH_STATE = Path("snapshots/latest/kill_switch_state.json")
DEFAULT_KILL_SWITCH_AUDIT = Path("logs/audit/kill_switch.jsonl")
DEFAULT_KILL_SWITCH_LOG = Path("logs/events/risk.kill_switch.jsonl")
DEFAULT_KILL_SWITCH_METRICS = Path("metrics/kill_switch.jsonl")

__all__ = [
    "DEFAULT_KILL_SWITCH_AUDIT",
    "DEFAULT_KILL_SWITCH_LOG",
    "DEFAULT_KILL_SWITCH_STATE",
    "DEFAULT_KILL_SWITCH_METRICS",
    "KillSwitchEvidenceError",
    "ResumeBlocked",
    "resume_blocked",
    "review",
    "set_state",
]

def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"state": "none", "reason": None, "updated_at": None, "actor": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"state": "none", "reason": None, "updated_at": None, "actor": None}


def _persist_state(path: Path, *, state: str, reason: str | None, actor: str | None) -> Path:
    payload = {
        "state": state,
        "reason": reason,
        "actor": actor,
        "updated_at": _utcnow_iso(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

DEFAULT_OUTPUT_DIR = Path("reports/audit/kill_switch_review")


class KillSwitchEvidenceError(RuntimeError):
    """Raised when kill-switch review evidence cannot be produced."""


class ResumeBlocked(RuntimeError):
    """Raised when resume is requested without meeting prerequisites."""


def resume_blocked(message: str) -> ResumeBlocked:
    return ResumeBlocked(message)


def set_state(
    *,
    state: str,
    reason: str | None = None,
    actor: str = "cli",
    runbook: str | None = None,
    evidence: Iterable[Path] | None = None,
    state_path: Path = DEFAULT_KILL_SWITCH_STATE,
    audit_path: Path = DEFAULT_KILL_SWITCH_AUDIT,
    log_path: Path = DEFAULT_KILL_SWITCH_LOG,
    metrics_path: Path = DEFAULT_KILL_SWITCH_METRICS,
    gate_state_path: Path | None = None,
) -> Mapping[str, object]:
    """Set the kill switch state with audit and history outputs."""

    state_value = state.lower()
    if state_value not in {"none", "soft_stop", "hard_stop"}:
        raise KillSwitchEvidenceError(f"Unsupported kill switch state: {state}")

    current = _load_state(state_path)
    current_state = str(current.get("state") or "none")
    evidence_paths = [str(item) for item in (evidence or ())]

    blocked = state_value == "none" and current_state == "hard_stop" and not evidence_paths
    exit_code = 62 if blocked else 0

    audit_payload: MutableMapping[str, object] = {
        "ts": _utcnow_iso(),
        "action": "kill_switch.set",
        "state_before": current_state,
        "state_after": state_value,
        "actor": actor,
        "reason": reason,
        "evidence": evidence_paths,
        "runbook": runbook,
    }

    if blocked:
        audit_payload["status"] = "blocked"
        _append_jsonl(audit_path, audit_payload)
        return {
            "status": "blocked",
            "state": current_state,
            "requested_state": state_value,
            "reason": reason,
            "audit_path": str(audit_path),
            "state_path": str(state_path),
            "exit_code": exit_code,
        }

    _persist_state(state_path, state=state_value, reason=reason, actor=actor)
    try:
        _append_jsonl(audit_path, audit_payload)
    except OSError as exc:  # pragma: no cover - defensive
        logger.exception("kill_switch.audit_write_failed", exc_info=exc)

    log_entry = {
        "ts": _utcnow_iso(),
        "event": f"kill_switch.{state_value}",
        "reason": reason,
        "actor": actor,
    }
    try:
        _append_jsonl(log_path, log_entry)
    except OSError as exc:  # pragma: no cover - defensive
        logger.exception("kill_switch.log_write_failed", exc_info=exc)

    metrics_payload = {
        "ts": _utcnow_iso(),
        "state": state_value,
        "previous_state": current_state,
        "reason": reason,
        "actor": actor,
        "runbook": runbook,
    }
    try:
        _append_jsonl(metrics_path, metrics_payload)
    except OSError as exc:  # pragma: no cover - best effort
        logger.exception("kill_switch.metrics_write_failed", exc_info=exc)

    gate_state_snapshot: str | None = None
    if gate_state_path:
        try:
            from src.core.gate import GateState, GateAggregator  # local import to avoid cycles

            if gate_state_path.exists():
                gate_state = GateState.load(gate_state_path)
            else:
                gate_state = GateState()
            aggregator = GateAggregator(initial_state=gate_state)
            aggregator._state.risk.kill_switch_recommendation = None if state_value == "none" else state_value  # type: ignore[attr-defined]
            aggregator._state.risk.kill_switch_reason = reason  # type: ignore[attr-defined]
            aggregator._state.auto_execute = state_value == "none" and not aggregator._state.risk.reduce_only  # type: ignore[attr-defined]
            gate_state_snapshot = str(aggregator.persist_latest(path=gate_state_path))
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("kill_switch.gate_state_update_failed", exc_info=exc)

    payload: MutableMapping[str, object] = {
        "status": "ok",
        "state": state_value,
        "previous_state": current_state,
        "reason": reason,
        "actor": actor,
        "audit_path": str(audit_path),
        "state_path": str(state_path),
        "log_path": str(log_path),
        "metrics_path": str(metrics_path),
        "exit_code": exit_code,
        "message": f"Kill Switch set to {state_value}",
    }
    if evidence_paths:
        payload["evidence"] = evidence_paths
    if runbook:
        payload["runbook"] = runbook
        payload["message"] = f"Kill Switch set to {state_value} (see {runbook})"
    if gate_state_snapshot:
        payload["gate_state_path"] = gate_state_snapshot
    _append_validation_log(payload)
    return payload


def _append_validation_log(payload: Mapping[str, object]) -> None:
    try:
        date_stamp = datetime.utcnow().strftime("%Y%m%d")
        log_path = Path("reports") / "validation_log" / f"AC-31_kill_switch_{date_stamp}.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"## Kill Switch Action {payload.get('state')}",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Status | {payload.get('status')} |",
            f"| Previous State | {payload.get('previous_state')} |",
            f"| State | {payload.get('state')} |",
            f"| Actor | {payload.get('actor')} |",
            f"| Reason | {payload.get('reason')} |",
            f"| Runbook | {payload.get('runbook') or ''} |",
            f"| Evidence | {', '.join(payload.get('evidence', [])) if isinstance(payload.get('evidence'), list) else ''} |",
            f"| GateState | {payload.get('gate_state_path') or ''} |",
            f"| Audit | {payload.get('audit_path')} |",
            f"| Metrics | {payload.get('metrics_path')} |",
        ]
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
            handle.write("\n\n")
    except Exception:
        return


def _current_time() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _normalise_attachments(values: Iterable[Path]) -> list[str]:
    return [str(item) for item in values]


def _build_filename(timestamp: datetime) -> str:
    return timestamp.strftime("%Y%m%dT%H%M%SZ.md")


def _render_markdown(
    *,
    path: Path,
    timestamp: datetime,
    reason: str,
    strategy: str | None,
    mode: str,
    recommendation: str,
    attachments: list[str],
) -> None:
    lines = [
        f"# Kill Switch Review - {reason}",
        "",
        f"- Generated At: {timestamp.isoformat()}",
        f"- Mode: {mode}",
        f"- Recommendation: {recommendation}",
    ]
    if strategy:
        lines.append(f"- Strategy: {strategy}")
    lines.extend(
        [
            "",
            "## Attachments",
            "",
        ]
    )
    if attachments:
        lines.extend(f"- {item}" for item in attachments)
    else:
        lines.append("- (none supplied)")
    lines.extend(
        [
            "",
            "## Follow-up Actions",
            "",
            "- Review Runbook RUN-RISK-01 and document recovery timeline.",
            "- Coordinate with Ops for live guard confirmation before toggling switches.",
            "",
            "_Mock review document for audit scaffolding. Replace with live workflow integration._",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def review(
    *,
    reason: str,
    strategy: str | None,
    mode: str,
    recommendation: str,
    attachments: Iterable[Path],
) -> Mapping[str, str]:
    """Produce a mock kill-switch review checklist."""

    if recommendation not in {"guarded", "resume"}:
        raise KillSwitchEvidenceError(f"Unsupported recommendation: {recommendation}")

    attachment_paths = _normalise_attachments(attachments)
    if recommendation == "resume" and not attachment_paths:
        message = "Evidence attachments are required before recommending resume."
        logger.warning("kill_switch.review.resume_blocked", extra={"reason": reason})
        raise resume_blocked(message)

    timestamp = _current_time()
    filename = _build_filename(timestamp)
    target = DEFAULT_OUTPUT_DIR / filename

    try:
        _render_markdown(
            path=target,
            timestamp=timestamp,
            reason=reason,
            strategy=strategy,
            mode=mode,
            recommendation=recommendation,
            attachments=attachment_paths,
        )
    except OSError as exc:
        logger.exception("kill_switch.review.write_failed", extra={"output": str(target)})
        raise KillSwitchEvidenceError(f"Failed to write kill-switch review: {target}") from exc

    payload: MutableMapping[str, str] = {
        "status": "ok",
        "output": str(target),
        "reason": reason,
        "mode": mode,
        "recommendation": recommendation,
        "generated_at": timestamp.isoformat(),
    }
    if strategy:
        payload["strategy"] = strategy
    logger.info("kill_switch.review.completed", extra=payload)
    return payload
