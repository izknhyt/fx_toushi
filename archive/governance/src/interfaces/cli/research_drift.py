"""Research drift CLI helpers (EP06)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.core.health import HealthMonitor
from src.research.drift import ParameterDriftMonitor

DEFAULT_FEATURE_FLAGS_PATH = Path("config/feature_flags.yaml")
DEFAULT_HEALTH_STATE_PATH = Path("snapshots/latest/health_state.json")
RUNBOOK_PATH = Path("docs/runbooks/RUN-DRIFT-01.md")

__all__ = ["scan", "DEFAULT_HEALTH_STATE_PATH"]


def scan(
    *,
    strategy_id: str,
    mode: str,
    profile: str,
    force: bool = False,
    config_path: Path = Path("config/drift_monitor.yaml"),
    manifest_path: Path = Path("config/strategy_manifest.yaml"),
    opt_run_dir: Path = Path("optimization_runs"),
    metrics_path: Path = Path("metrics/parameter_drift.jsonl"),
    event_log: Path = Path("logs/events/research_drift.jsonl"),
    feature_flags_path: Path = DEFAULT_FEATURE_FLAGS_PATH,
    health_state_path: Path = DEFAULT_HEALTH_STATE_PATH,
) -> Mapping[str, Any]:
    enabled = _read_feature_flag(
        "research.parameter_drift", profile=profile, path=feature_flags_path
    )
    if not enabled and not force:
        return {
            "status": "skipped",
            "enabled": False,
            "reason": "feature_flag_disabled",
            "runbook": str(RUNBOOK_PATH),
        }

    monitor = ParameterDriftMonitor(
        config_path=config_path,
        manifest_path=manifest_path,
        opt_run_dir=opt_run_dir,
        metrics_path=metrics_path,
        event_log=event_log,
    )
    alert = monitor.scan(strategy_id=strategy_id, mode=mode)
    payload: dict[str, Any] = {
        "status": alert.status,
        "enabled": enabled,
        "alert": alert.to_dict(),
        "runbook": str(RUNBOOK_PATH),
    }
    if alert.status in {"warning", "degraded", "missing"}:
        _apply_health_state(alert, payload, health_state_path=health_state_path)
    return payload


def _apply_health_state(alert: Any, payload: dict[str, Any], *, health_state_path: Path) -> None:
    level = "warning" if alert.status in {"warning", "missing"} else "degraded"
    detail = _format_detail(alert)
    monitor = HealthMonitor()
    monitor.raise_condition(
        level,
        "parameter_drift",
        detail=detail,
        recommended_action="runbook:RUN-DRIFT-01",
    )
    snapshot = monitor.snapshot().to_dict()
    health_state_path.parent.mkdir(parents=True, exist_ok=True)
    health_state_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    payload["health_state_path"] = str(health_state_path)


def _format_detail(alert: Any) -> str:
    parts = []
    if alert.kl is not None:
        parts.append(f"kl={alert.kl}")
    if alert.mahalanobis is not None:
        parts.append(f"mahalanobis={alert.mahalanobis}")
    if alert.drifted_params:
        parts.append(f"params={','.join(sorted(alert.drifted_params))}")
    return ";".join(parts) if parts else "parameter_drift_detected"


def _read_feature_flag(flag: str, *, profile: str, path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    defaults = payload.get("defaults") or {}
    profile_defaults = defaults.get(profile)
    if not isinstance(profile_defaults, Mapping):
        return False
    return bool(profile_defaults.get(flag, False))
