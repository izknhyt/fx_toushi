"""Shadow Gateway CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.shadow_gateway.feature_flag import ShadowGatewayFeature


def gateway_status(
    *,
    profile: str,
    feature_flags_path: Path = Path("config/feature_flags.yaml"),
) -> Mapping[str, Any]:
    features = ShadowGatewayFeature(path=feature_flags_path)
    return {
        "status": "ok",
        "profile": profile,
        "streaming": features.is_enabled("shadow.gateway.streaming", mode=profile),
        "offline_cache": features.is_enabled("shadow.gateway.offline_cache", mode=profile),
        "force_failover": features.is_enabled("shadow.gateway.force_failover", mode=profile),
        "feature_flags_path": str(feature_flags_path),
    }


def gateway_failover(
    *,
    profile: str,
    restore: bool = False,
    feature_flags_path: Path = Path("config/feature_flags.yaml"),
) -> Mapping[str, Any]:
    features = ShadowGatewayFeature(path=feature_flags_path)
    payload = features.set_flag(
        "shadow.gateway.force_failover",
        mode=profile,
        value=False if restore else True,
    )
    payload["status"] = "ok"
    payload["action"] = "restore" if restore else "failover"
    return payload


__all__ = ["gateway_status", "gateway_failover"]
