"""Telemetry hooks for GUI board events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


@dataclass(slots=True)
class GuiTelemetryEvent:
    session_id: str
    user_role: str | None
    state_transition: str | None
    latency_ms: float | None
    shadow_roundtrip_ms: float | None
    banner_level: str | None
    command: str | None
    result: str | None
    error_code: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_role": self.user_role,
            "state_transition": self.state_transition,
            "latency_ms": self.latency_ms,
            "shadow_roundtrip_ms": self.shadow_roundtrip_ms,
            "banner_level": self.banner_level,
            "command": self.command,
            "result": self.result,
            "error_code": self.error_code,
        }


class GuiTelemetryRecorder:
    latency_warn_threshold_ms: float = 800.0
    shadow_warn_threshold_ms: float = 3000.0

    def __init__(
        self,
        *,
        metrics_path: Path = Path("metrics/gui_board.jsonl"),
        session_id: str = "gui-session",
    ) -> None:
        self._metrics_path = metrics_path
        self._session_id = session_id

    def record(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        event = GuiTelemetryEvent(
            session_id=self._session_id,
            user_role=payload.get("user_role"),
            state_transition=payload.get("state_transition"),
            latency_ms=payload.get("latency_ms"),
            shadow_roundtrip_ms=payload.get("shadow_roundtrip_ms"),
            banner_level=payload.get("banner_level"),
            command=payload.get("command"),
            result=payload.get("result"),
            error_code=payload.get("error_code"),
        )
        entry = {"ts": _utcnow_iso(), **event.to_dict()}
        entry["warn_latency"] = _over_threshold(
            event.latency_ms, self.latency_warn_threshold_ms
        )
        entry["warn_shadow_roundtrip"] = _over_threshold(
            event.shadow_roundtrip_ms, self.shadow_warn_threshold_ms
        )
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")
        return entry


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _over_threshold(value: float | None, threshold: float) -> bool:
    if value is None:
        return False
    try:
        return float(value) > threshold
    except (TypeError, ValueError):
        return False


__all__ = ["GuiTelemetryEvent", "GuiTelemetryRecorder"]
