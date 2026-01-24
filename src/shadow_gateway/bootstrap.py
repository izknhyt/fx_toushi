"""Bootstrap helper for Shadow Gateway components."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.shadow_gateway.audit import AuditSink
from src.shadow_gateway.backpressure import BackpressureGovernor
from src.shadow_gateway.cache import OfflineCacheManager
from src.shadow_gateway.feature_flag import ShadowGatewayFeature
from src.shadow_gateway.metrics import GatewayMetrics
from src.shadow_gateway.session_supervisor import SessionSupervisor


@dataclass(slots=True)
class GatewayBootstrap:
    mode: str
    feature_flags_path: Path = Path("config/feature_flags.yaml")

    def configure(self) -> dict[str, object]:
        metrics = GatewayMetrics()
        audit = AuditSink()
        features = ShadowGatewayFeature(path=self.feature_flags_path)
        supervisor = SessionSupervisor(metrics=metrics, audit=audit, feature_flags=features)
        backpressure = BackpressureGovernor(metrics=metrics, audit=audit)
        cache = OfflineCacheManager(
            metrics=metrics,
            audit=audit,
            feature_flags=features,
            profile=self.mode,
        )
        return {
            "metrics": metrics,
            "audit": audit,
            "features": features,
            "supervisor": supervisor,
            "backpressure": backpressure,
            "cache": cache,
        }


__all__ = ["GatewayBootstrap"]
