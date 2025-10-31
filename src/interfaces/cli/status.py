"""Implementation for the ``tradectl status`` command (see §17.3)."""

from __future__ import annotations

import logging
from typing import Mapping

from src.core.gate import GateState
from src.core.health import HealthMonitor

logger = logging.getLogger(__name__)

__all__ = ["status"]


def status(
    *,
    verbose: bool = False,
    json_output: bool = False,
    ack: str | None = None,
    kill_switch: str | None = None,
    board: str | None = None,
    monitor: HealthMonitor | None = None,
    gate_state: GateState | None = None,
) -> Mapping[str, object]:
    """Return the current status snapshot for operators."""

    monitor = monitor or HealthMonitor()
    gate_state = gate_state or GateState()

    health_state = monitor.snapshot()
    risk_state = gate_state.risk
    kill_switch_payload = {
        "suggestion": risk_state.kill_switch_recommendation,
        "reason": risk_state.kill_switch_reason,
    }

    result: Mapping[str, object] = {
        "health": health_state.to_dict(),
        "risk": gate_state.risk.to_dict(),
        "kill_switch": kill_switch_payload,
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
