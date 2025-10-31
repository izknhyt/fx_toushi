"""Implementation for the ``tradectl status`` command (see §17.3)."""

from __future__ import annotations

import logging
from typing import Any, Mapping, MutableMapping

from src.core.gate import GateState
from src.core.health import HealthMonitor, HealthReason
from src.core.snapshot import SnapshotManager, SnapshotRestoreResult

logger = logging.getLogger(__name__)

__all__ = ["status"]


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
    reasons: list[HealthReason],
    board_mode_suggestion: str | None,
    board_mode_runbook: str | None,
    status: str,
    reduce_only: bool,
    kill_switch_recommendation: str | None,
) -> Mapping[str, Any] | None:
    """Construct the Acceptable Degradation banner payload when needed."""

    if status not in {"degraded", "soft_stop", "hard_stop"} and not reduce_only:
        return None

    reason_codes = [reason.code for reason in reasons]
    banner_message = board_mode_suggestion or (reason_codes[0] if reason_codes else None)
    return {
        "kind": "acceptable_degradation",
        "severity": status,
        "message": banner_message,
        "reason_codes": reason_codes,
        "runbook": board_mode_runbook,
        "reduce_only": reduce_only,
        "kill_switch_recommendation": kill_switch_recommendation,
        "visible": True,
    }


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
) -> Mapping[str, object]:
    """Return the current status snapshot for operators."""

    monitor = monitor or HealthMonitor()
    gate_state = gate_state or GateState()
    snapshot_manager = snapshot_manager or SnapshotManager()

    health_state = monitor.snapshot()
    risk_state = gate_state.risk
    kill_switch_payload = {
        "suggestion": risk_state.kill_switch_recommendation,
        "reason": risk_state.kill_switch_reason,
        "requested_transition": kill_switch,
    }

    banner = _build_banner(
        reasons=list(health_state.reasons),
        board_mode_suggestion=health_state.board_mode_suggestion,
        board_mode_runbook=health_state.board_mode_runbook,
        status=health_state.status,
        reduce_only=risk_state.reduce_only,
        kill_switch_recommendation=risk_state.kill_switch_recommendation,
    )

    ops_actions: Mapping[str, Any] = {
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
    }

    result: MutableMapping[str, object] = {
        "health": health_state.to_dict(),
        "gate": gate_state.to_dict(),
        "risk": risk_state.to_dict(),
        "kill_switch": kill_switch_payload,
        "snapshots": _snapshot_section(snapshot_manager),
        "ops": {
            "banner": banner,
            "actions": ops_actions,
        },
        "meta": {
            "json_output": json_output,
            "verbose": verbose,
        },
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
        },
    )

    return result
