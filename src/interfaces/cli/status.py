"""Implementation for the ``tradectl status`` command (see §17.3)."""

from __future__ import annotations

import json
import logging
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from src.core.gate import GateState
from src.core.health import (
    GuardrailSnapshot,
    HealthAction,
    HealthMonitor,
    HealthReason,
    HealthState,
    KillSwitchSuggestion,
)
from src.core.snapshot import SnapshotManager, SnapshotRestoreResult

logger = logging.getLogger(__name__)

DEFAULT_KILL_SWITCH_LOG = Path("logs/events/risk.kill_switch.jsonl")
DEFAULT_GUARDRAILS_METRICS = Path("metrics/guardrails.jsonl")
DEFAULT_HEALTH_ACTION_AUDIT = Path("logs/audit/health_action.jsonl")
DEFAULT_GATE_STATE_PATH = Path("snapshots/latest/gate_state.json")
DEFAULT_HEALTH_STATE_PATH = Path("snapshots/latest/health_state.json")
DEFAULT_KILL_SWITCH_STATE_PATH = Path("snapshots/latest/kill_switch_state.json")

__all__ = [
    "status",
    "DEFAULT_KILL_SWITCH_LOG",
    "DEFAULT_GUARDRAILS_METRICS",
    "DEFAULT_HEALTH_ACTION_AUDIT",
    "DEFAULT_GATE_STATE_PATH",
    "DEFAULT_HEALTH_STATE_PATH",
    "DEFAULT_KILL_SWITCH_STATE_PATH",
]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


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


def _load_health_state(monitor: HealthMonitor, path: Path) -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    reasons: list[HealthReason] = []
    for item in data.get("reasons", []):
        reasons.append(
            HealthReason(
                code=item.get("code", "unknown"),
                level=item.get("level", "degraded"),
                detail=item.get("detail"),
                recommended_action=item.get("recommended_action"),
                raised_at=_parse_dt(item.get("raised_at")) or datetime.now(timezone.utc),
            )
        )
    kill_switch_data = data.get("kill_switch")
    kill_switch = (
        KillSwitchSuggestion(
            state=kill_switch_data.get("state", "none"),
            reason=kill_switch_data.get("reason", "unspecified"),
            runbook=kill_switch_data.get("runbook"),
        )
        if kill_switch_data
        else None
    )
    monitor._state = HealthState(  # type: ignore[attr-defined]
        status=data.get("status", "ok"),
        reasons=reasons,
        board_mode_suggestion=data.get("board_mode_suggestion"),
        board_mode_runbook=data.get("board_mode_runbook"),
        kill_switch=kill_switch,
    )
    actions: list[HealthAction] = []
    for action in data.get("actions", []):
        actions.append(
            HealthAction(
                id=action.get("id", action.get("reason", "action")),
                action=action.get("action", "guarded"),
                reason=action.get("reason", "unspecified"),
                evidence=list(action.get("evidence", [])),
                expires_at=_parse_dt(action.get("expires_at")),
                queued_at=_parse_dt(action.get("queued_at")) or datetime.now(timezone.utc),
            )
        )
    monitor._actions = actions  # type: ignore[attr-defined]


def _load_kill_switch_state(path: Path) -> tuple[str, str | None]:
    if not path or not path.exists():
        return "none", None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "none", None
    state = data.get("state", "none")
    reason = data.get("reason")
    return state, reason


def _serialise_snapshot_restore(result: SnapshotRestoreResult) -> Mapping[str, Any]:
    """Convert :class:`SnapshotRestoreResult` into a CLI friendly payload."""

    state = result.state
    serialised_state: Any
    if hasattr(state, "to_dict") and callable(getattr(state, "to_dict")):
        try:
            serialised_state = state.to_dict()  # type: ignore[call-arg]
        except Exception:  # pragma: no cover - defensive against user objects
            serialised_state = repr(state)
    elif isinstance(state, Mapping):
        serialised_state = dict(state)
    else:
        serialised_state = repr(state)
    return {
        "status": "ok",
        "state": serialised_state,
        "warnings": list(result.warnings),
    }


def _snapshot_section(manager: SnapshotManager) -> Mapping[str, Any]:
    """Collect snapshot diagnostics while tolerating unimplemented backends."""

    try:
        restore = manager.restore()
    except NotImplementedError as exc:
        return {
            "status": "unavailable",
            "error": str(exc),
            "base_path": str(manager.base_path),
        }
    except FileNotFoundError as exc:
        return {
            "status": "missing",
            "error": str(exc),
            "base_path": str(manager.base_path),
        }
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("cli.status.snapshot_error", exc_info=exc)
        return {
            "status": "error",
            "error": str(exc),
            "base_path": str(manager.base_path),
        }
    else:
        payload: MutableMapping[str, Any] = dict(_serialise_snapshot_restore(restore))
        payload["base_path"] = str(manager.base_path)
        return payload


def _build_banner(
    *,
    health: HealthState,
    guardrail: GuardrailSnapshot,
    reduce_only: bool,
) -> Mapping[str, Any] | None:
    """Construct the Acceptable Degradation banner payload when needed."""

    if guardrail.board_mode == "normal" and not reduce_only:
        return None

    reason_codes = [reason.code for reason in health.reasons]
    if guardrail.spread_reason:
        reason_codes.append(guardrail.spread_reason)
    if guardrail.reduce_only_reason:
        reason_codes.append(guardrail.reduce_only_reason)
    if guardrail.kill_switch_reason:
        reason_codes.append(guardrail.kill_switch_reason)
    banner_message = health.board_mode_suggestion or guardrail.banner or (reason_codes[0] if reason_codes else None)
    return {
        "kind": "acceptable_degradation",
        "severity": guardrail.health_status,
        "message": banner_message,
        "reason_codes": reason_codes,
        "runbook": guardrail.runbook or health.board_mode_runbook,
        "reduce_only": reduce_only,
        "kill_switch_recommendation": guardrail.kill_switch_state,
        "board_mode": guardrail.board_mode,
        "visible": True,
    }


def _kill_switch_history(path: Path, *, limit: int = 10) -> Mapping[str, Any]:
    if not path.exists():
        return {
            "status": "unavailable",
            "error": "kill switch log missing",
            "path": str(path),
        }
    entries: list[Mapping[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle.readlines() if line.strip()]
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:  # pragma: no cover - defensive
            continue
    return {
        "status": "ok",
        "path": str(path),
        "entries": entries,
    }


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def status(
    *,
    verbose: bool = False,
    json_output: bool = False,
    ack: str | None = None,
    kill_switch: str | None = None,
    board: str | None = None,
    monitor: HealthMonitor | None = None,
    gate_state: GateState | None = None,
    snapshot_manager: SnapshotManager | None = None,
    history: str | None = None,
    kill_switch_log_path: Path = DEFAULT_KILL_SWITCH_LOG,
    metrics_path: Path = DEFAULT_GUARDRAILS_METRICS,
    audit_path: Path = DEFAULT_HEALTH_ACTION_AUDIT,
    gate_state_path: Path | None = None,
    health_state_path: Path | None = None,
    kill_switch_state_path: Path | None = DEFAULT_KILL_SWITCH_STATE_PATH,
    actor: str = "cli",
) -> Mapping[str, object]:
    """Return the current status snapshot for operators."""

    monitor = monitor or HealthMonitor()
    guardrails: dict[str, object] = {}
    if metrics_path and metrics_path.exists():
        try:
            last_line = [line for line in metrics_path.read_text(encoding="utf-8").splitlines() if line.strip()][-1]
            guardrails = json.loads(last_line)
        except Exception:  # pragma: no cover - defensive
            guardrails = {}
    if health_state_path is not None:
        _load_health_state(monitor, health_state_path)
    gate_state = gate_state or (GateState.load(gate_state_path) if gate_state_path else GateState())
    snapshot_manager = snapshot_manager or SnapshotManager()
    # propagate manifest hashes from guardrails metrics when present
    if guardrails.get("manifest_hash") and not gate_state.cfg_hash:
        gate_state.cfg_hash = guardrails.get("manifest_hash")
    if guardrails.get("data_hash") and not gate_state.data_hash:
        gate_state.data_hash = guardrails.get("data_hash")
    # fallback to env/manifest if still missing
    if not gate_state.cfg_hash:
        cfg_path_env = os.getenv("TRADECTL_CFG_PATH")
        cfg_env = os.getenv("TRADECTL_CFG_HASH")
        if cfg_path_env and Path(cfg_path_env).exists():
            gate_state.cfg_hash = _sha256_path(Path(cfg_path_env))
        elif cfg_env:
            gate_state.cfg_hash = cfg_env
    if not gate_state.data_hash:
        data_env = os.getenv("TRADECTL_DATA_HASH")
        if data_env:
            gate_state.data_hash = data_env
        else:
            manifest_path = Path("reports") / "data_manifest.json"
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    entry = (manifest.get("strategies") or {}).get("m1_baseline_ma_rsi") or {}
                    gate_state.data_hash = entry.get("dataset_sha256")
                except json.JSONDecodeError:
                    gate_state.data_hash = None

    raw_kill_switch_state, kill_switch_reason = _load_kill_switch_state(kill_switch_state_path) if kill_switch_state_path else ("none", None)
    kill_switch_override = None if raw_kill_switch_state in {None, "none"} else raw_kill_switch_state
    monitor.enforce_auto_execute_policy(gate_state)
    health_state = monitor.snapshot()
    risk_state = gate_state.risk
    guardrail = monitor.guardrail_snapshot(gate_state, kill_switch_state=kill_switch_override)
    kill_switch_state_value = kill_switch_override or guardrail.kill_switch_state
    kill_switch_reason = kill_switch_reason or guardrail.kill_switch_reason or risk_state.kill_switch_reason

    ack_result: Mapping[str, Any] | None = None
    if ack:
        ack_result = monitor.ack_action(ack, actor=actor)
        audit_payload: dict[str, object] = {
            "event": "health_action.ack",
            "ts": _utcnow_iso(),
            **ack_result,
        }
        try:
            _append_jsonl(audit_path, audit_payload)
        except OSError as exc:  # pragma: no cover - defensive
            logger.exception("cli.status.audit_write_failed", exc_info=exc)

    banner = _build_banner(
        health=health_state,
        guardrail=guardrail,
        reduce_only=risk_state.reduce_only,
    )

    ops_actions: MutableMapping[str, Any] = {
        "ack": {
            "requested": bool(ack),
            "reference": ack,
            "status": "queued" if ack else "idle",
        },
        "kill_switch": {
            "requested": bool(kill_switch),
            "requested_state": kill_switch,
            "status": "queued" if kill_switch else "idle",
        },
        "board": {
            "requested": bool(board),
            "reference": board,
            "status": "queued" if board else "idle",
        },
        "pending": [action.to_dict() for action in monitor.actions()],
    }
    if ack_result:
        ops_actions["ack"]["result"] = ack_result

    kill_switch_payload = {
        "state": kill_switch_state_value,
        "reason": kill_switch_reason,
        "suggestion": risk_state.kill_switch_recommendation,
        "requested_transition": kill_switch,
    }

    guardrail_payload = guardrail.to_dict()
    guardrail_payload["pending_actions"] = ops_actions["pending"]
    result: MutableMapping[str, object] = {
        "health": health_state.to_dict(),
        "gate": gate_state.to_dict(),
        "risk": risk_state.to_dict(),
        "kill_switch": kill_switch_payload,
        "guardrails": guardrail_payload,
        "snapshots": _snapshot_section(snapshot_manager),
        "ops": {
            "banner": banner,
            "actions": ops_actions,
        },
        "meta": {
            "json_output": json_output,
            "verbose": verbose,
        },
        "exit_code": guardrail.exit_code,
    }

    if history:
        history_key = history.lower()
        if history_key == "kill-switch":
            result.setdefault("history", {})  # type: ignore[arg-type]
            result["history"]["kill_switch"] = _kill_switch_history(kill_switch_log_path)
        else:
            result.setdefault("history", {})  # type: ignore[arg-type]
            result["history"][history_key] = {
                "status": "unsupported",
                "error": f"history kind '{history}' is not available",
            }

    logger.info(
        "cli.status.summary",
        extra={
            "verbose": verbose,
            "json": json_output,
            "ack": ack,
            "kill_switch": kill_switch,
            "board": board,
            "health_status": health_state.status,
            "reduce_only": risk_state.reduce_only,
            "exit_code": guardrail.exit_code,
        },
    )

    metrics_payload = {
        "timestamp": _utcnow_iso(),
        "health_state": guardrail.health_status,
        "board_mode": guardrail.board_mode,
        "kill_switch": guardrail.kill_switch_state,
        "spread_status": guardrail.spread_status,
        "reason": guardrail.banner or guardrail.spread_reason or guardrail.kill_switch_reason or "ok",
        "suggested_action": guardrail.runbook,
        "reasons": guardrail.reasons,
        "exit_code": guardrail.exit_code,
        "reduce_only": guardrail.reduce_only,
        "ack_user": actor if ack else None,
        "manifest_hash": gate_state.cfg_hash,
        "data_hash": gate_state.data_hash,
    }
    if metrics_payload["manifest_hash"] is None:
        metrics_payload.pop("manifest_hash")
    if metrics_payload["data_hash"] is None:
        metrics_payload.pop("data_hash")
    try:
        _append_jsonl(metrics_path, metrics_payload)
    except OSError as exc:  # pragma: no cover - defensive
        logger.exception("cli.status.metrics_write_failed", exc_info=exc)

    return result
