"""Backpressure governor for Shadow Gateway."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.shadow_gateway.audit import AuditSink
from src.shadow_gateway.metrics import GatewayMetrics


@dataclass(slots=True)
class BackpressureGovernor:
    threshold_ratio: float = 0.8
    metrics: GatewayMetrics = field(default_factory=GatewayMetrics)
    audit: AuditSink = field(default_factory=AuditSink)

    def observe(
        self,
        *,
        queue_depth: int,
        capacity: int,
        session_id: str | None = None,
        channel: str | None = None,
    ) -> str:
        ratio = 0.0 if capacity <= 0 else queue_depth / capacity
        state = "throttled" if ratio >= self.threshold_ratio else "normal"
        self.metrics.record(
            "shadow.gateway.queue_depth",
            ratio,
            session_id=session_id,
            channel=channel,
            queue_depth=queue_depth,
            queue_depth_ratio=ratio,
            backpressure_state=state,
        )
        if state == "throttled":
            self.audit.append(
                "audit.shadow_gateway.backpressure",
                {
                    "session_id": session_id,
                    "queue_depth": queue_depth,
                    "capacity": capacity,
                    "ratio": ratio,
                    "state": state,
                },
            )
        return state


__all__ = ["BackpressureGovernor"]
