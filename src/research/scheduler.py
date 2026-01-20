"""Parameter sweep scheduler for experiment runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.research.experiment import ExperimentTrackerError, _uuid7

DEFAULT_QUEUE_PATH = Path("logs") / "research" / "experiment_queue.jsonl"


class ExperimentScheduleError(ExperimentTrackerError):
    """Raised when experiment scheduling fails."""


@dataclass(slots=True)
class SweepReservation:
    run_id: str
    experiment_id: str
    sweep_method: str
    parameters: dict[str, object]
    status: str
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "experiment_id": self.experiment_id,
            "sweep_method": self.sweep_method,
            "parameters": dict(self.parameters),
            "status": self.status,
            "created_at": self.created_at,
        }


class ParameterSweepScheduler:
    def __init__(self, *, queue_path: Path = DEFAULT_QUEUE_PATH) -> None:
        self._queue_path = queue_path

    def schedule(self, experiment_id: str, *, sweep_config: Path) -> list[SweepReservation]:
        if not sweep_config.exists():
            raise ExperimentScheduleError(f"sweep_config missing: {sweep_config}")
        payload = _load_payload(sweep_config)
        sweep_method = str(payload.get("method") or "grid")
        combinations = _expand_sweep(payload)
        reservations: list[SweepReservation] = []
        for params in combinations:
            reservations.append(
                SweepReservation(
                    run_id=_uuid7(),
                    experiment_id=experiment_id,
                    sweep_method=sweep_method,
                    parameters=params,
                    status="queued",
                    created_at=_utcnow_iso(),
                )
            )
        self._append_queue(reservations)
        return reservations

    def list_queue(self) -> list[SweepReservation]:
        if not self._queue_path.exists():
            return []
        reservations: list[SweepReservation] = []
        for line in self._queue_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            reservations.append(
                SweepReservation(
                    run_id=str(payload.get("run_id") or ""),
                    experiment_id=str(payload.get("experiment_id") or ""),
                    sweep_method=str(payload.get("sweep_method") or "grid"),
                    parameters=dict(payload.get("parameters") or {}),
                    status=str(payload.get("status") or "queued"),
                    created_at=str(payload.get("created_at") or ""),
                )
            )
        return reservations

    def _append_queue(self, reservations: list[SweepReservation]) -> None:
        self._queue_path.parent.mkdir(parents=True, exist_ok=True)
        with self._queue_path.open("a", encoding="utf-8") as handle:
            for reservation in reservations:
                handle.write(json.dumps(reservation.to_dict(), ensure_ascii=False) + "\n")


def _expand_sweep(payload: Mapping[str, Any]) -> list[dict[str, object]]:
    if "params" in payload and isinstance(payload["params"], list):
        return [dict(item) for item in payload["params"] if isinstance(item, Mapping)]
    grid = payload.get("grid")
    if isinstance(grid, Mapping):
        return _expand_grid(grid)
    return [{}]


def _expand_grid(grid: Mapping[str, Any]) -> list[dict[str, object]]:
    items: list[tuple[str, list[object]]] = []
    for key, value in grid.items():
        if isinstance(value, list):
            items.append((str(key), list(value)))
        else:
            items.append((str(key), [value]))
    if not items:
        return [{}]
    results = [{}]
    for key, values in items:
        next_results = []
        for base in results:
            for value in values:
                updated = dict(base)
                updated[key] = value
                next_results.append(updated)
        results = next_results
    return results


def _load_payload(path: Path) -> Mapping[str, Any]:
    try:
        if path.suffix in {".yaml", ".yml"}:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ExperimentScheduleError(f"invalid sweep_config: {path}") from exc


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["ParameterSweepScheduler", "ExperimentScheduleError", "SweepReservation"]
