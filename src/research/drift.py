"""Parameter drift monitoring helpers."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.persistence.events import EventWriter

DEFAULT_CONFIG_PATH = Path("config/drift_monitor.yaml")
DEFAULT_MANIFEST_PATH = Path("config/strategy_manifest.yaml")
DEFAULT_OPT_RUN_DIR = Path("optimization_runs")
DEFAULT_METRICS_PATH = Path("metrics/parameter_drift.jsonl")
DEFAULT_EVENT_LOG = Path("logs/events/research_drift.jsonl")


class ParameterDriftError(RuntimeError):
    """Raised when parameter drift evaluation fails."""


@dataclass(slots=True)
class ParameterStats:
    mean: float
    std: float


@dataclass(slots=True)
class DriftAlert:
    strategy_id: str
    mode: str
    status: str
    kl: float | None
    mahalanobis: float | None
    z_scores: Mapping[str, float]
    drifted_params: list[str]
    board_mode: str
    recommendations: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "mode": self.mode,
            "status": self.status,
            "kl": self.kl,
            "mahalanobis": self.mahalanobis,
            "z_scores": dict(self.z_scores),
            "drifted_params": list(self.drifted_params),
            "board_mode": self.board_mode,
            "recommendations": list(self.recommendations),
        }


class ParameterDriftMonitor:
    def __init__(
        self,
        *,
        config_path: Path = DEFAULT_CONFIG_PATH,
        manifest_path: Path = DEFAULT_MANIFEST_PATH,
        opt_run_dir: Path = DEFAULT_OPT_RUN_DIR,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        event_log: Path = DEFAULT_EVENT_LOG,
    ) -> None:
        self._config_path = config_path
        self._manifest_path = manifest_path
        self._opt_run_dir = opt_run_dir
        self._metrics_path = metrics_path
        self._event_log = event_log

    def scan(self, *, strategy_id: str, mode: str) -> DriftAlert:
        thresholds = _load_thresholds(self._config_path)
        stats = _load_parameter_stats(self._opt_run_dir, strategy_id=strategy_id)
        current = _load_strategy_parameters(self._manifest_path, strategy_id=strategy_id)
        if not stats or not current:
            alert = DriftAlert(
                strategy_id=strategy_id,
                mode=mode,
                status="missing",
                kl=None,
                mahalanobis=None,
                z_scores={},
                drifted_params=[],
                board_mode="normal",
                recommendations=["missing stats or parameters; verify optimization_runs"],
            )
            _write_metrics(self._metrics_path, alert)
            return alert
        z_scores: dict[str, float] = {}
        for key, stat in stats.items():
            if key not in current:
                continue
            value = current[key]
            if stat.std <= 0:
                continue
            z_scores[key] = (value - stat.mean) / stat.std
        if not z_scores:
            alert = DriftAlert(
                strategy_id=strategy_id,
                mode=mode,
                status="missing",
                kl=None,
                mahalanobis=None,
                z_scores={},
                drifted_params=[],
                board_mode="normal",
                recommendations=["no comparable parameters found"],
            )
            _write_metrics(self._metrics_path, alert)
            return alert
        sum_sq = sum(score * score for score in z_scores.values())
        mahalanobis = math.sqrt(sum_sq)
        kl = 0.5 * sum_sq
        drifted_params = [
            name for name, score in z_scores.items() if abs(score) >= thresholds["z_score"]
        ]
        status = "ok"
        board_mode = "normal"
        if mahalanobis >= thresholds["mahalanobis_threshold"]:
            status = "degraded"
            board_mode = "guarded"
        elif kl >= thresholds["kl_threshold"]:
            status = "warning"
        recommendations = _recommendations(status=status, drifted_params=drifted_params)
        alert = DriftAlert(
            strategy_id=strategy_id,
            mode=mode,
            status=status,
            kl=round(kl, 4),
            mahalanobis=round(mahalanobis, 4),
            z_scores=z_scores,
            drifted_params=drifted_params,
            board_mode=board_mode,
            recommendations=recommendations,
        )
        _write_metrics(self._metrics_path, alert)
        event_name = "research.drift.detected" if status != "ok" else "research.drift.cleared"
        _emit_event(self._event_log, event_name, alert)
        return alert


def _load_thresholds(path: Path) -> dict[str, float]:
    defaults = {"z_score": 3.0, "kl_threshold": 0.25, "mahalanobis_threshold": 2.5}
    if not path.exists():
        return defaults
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return defaults
    thresholds = payload.get("thresholds") or {}
    for key in ("z_score", "kl_threshold", "mahalanobis_threshold"):
        if key in thresholds:
            try:
                defaults[key] = float(thresholds[key])
            except (TypeError, ValueError):
                continue
    return defaults


def _load_parameter_stats(opt_dir: Path, *, strategy_id: str) -> dict[str, ParameterStats]:
    run_path = _find_latest_run(opt_dir / strategy_id)
    if run_path is None:
        return {}
    payload = json.loads(run_path.read_text(encoding="utf-8"))
    stats: dict[str, ParameterStats] = {}
    candidates = [
        payload.get("parameter_stats"),
        payload.get("parameters"),
        payload.get("stats"),
    ]
    for candidate in candidates:
        _extract_stats(stats, candidate)
    if "parameters" in payload and isinstance(payload["parameters"], list):
        for entry in payload["parameters"]:
            if isinstance(entry, Mapping) and "name" in entry and "mean" in entry and "std" in entry:
                stats[str(entry["name"])] = ParameterStats(
                    mean=float(entry["mean"]), std=float(entry["std"])
                )
    return stats


def _extract_stats(stats: dict[str, ParameterStats], candidate: Any, prefix: str = "") -> None:
    if isinstance(candidate, Mapping):
        if "mean" in candidate and "std" in candidate and len(candidate) <= 3:
            key = prefix.rstrip(".")
            try:
                stats[key] = ParameterStats(
                    mean=float(candidate["mean"]), std=float(candidate["std"])
                )
            except (TypeError, ValueError):
                return
            return
        for key, value in candidate.items():
            next_prefix = f"{prefix}{key}."
            _extract_stats(stats, value, next_prefix)


def _find_latest_run(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    candidates = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _load_strategy_parameters(path: Path, *, strategy_id: str) -> dict[str, float]:
    if not path.exists():
        return {}
    manifest = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    strategies = manifest.get("strategies") or {}
    entry = strategies.get(strategy_id) or {}
    params: dict[str, float] = {}
    for section_name in ("parameters", "entry", "sizing", "filters"):
        section = entry.get(section_name)
        if isinstance(section, Mapping):
            _flatten_params(params, section, prefix=f"{section_name}.")
    return params


def _flatten_params(target: dict[str, float], payload: Mapping[str, Any], *, prefix: str) -> None:
    for key, value in payload.items():
        if isinstance(value, Mapping):
            _flatten_params(target, value, prefix=f"{prefix}{key}.")
        elif isinstance(value, (int, float)):
            target[f"{prefix}{key}"] = float(value)


def _recommendations(status: str, drifted_params: list[str]) -> list[str]:
    if status == "ok":
        return ["parameters within drift thresholds"]
    recommendations = ["review optimization runs and strategy manifest", "runbook:RUN-DRIFT-01"]
    if drifted_params:
        recommendations.append(f"drifted params: {', '.join(sorted(drifted_params))}")
    return recommendations


def _write_metrics(path: Path, alert: DriftAlert) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        "event": "parameter_drift",
        "strategy_id": alert.strategy_id,
        "mode": alert.mode,
        "status": alert.status,
        "kl": alert.kl,
        "mahalanobis": alert.mahalanobis,
        "board_mode": alert.board_mode,
        "drifted_params": list(alert.drifted_params),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _emit_event(path: Path, event_name: str, alert: DriftAlert) -> None:
    writer = EventWriter(path)
    payload = {
        "event": event_name,
        "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        "strategy_id": alert.strategy_id,
        "mode": alert.mode,
        "status": alert.status,
        "kl": alert.kl,
        "mahalanobis": alert.mahalanobis,
    }
    writer.append(payload)


__all__ = ["DriftAlert", "ParameterDriftMonitor", "ParameterDriftError"]
