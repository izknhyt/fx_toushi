"""Mock implementation for execution tooling commands."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from src.execution.bridge import (
    DEFAULT_METRICS_PATH as DEFAULT_EXECUTION_BRIDGE_METRICS,
)
from src.execution.bridge import (
    DEFAULT_REPORT_DIR as DEFAULT_EXECUTION_REPORT_DIR,
)
from src.execution.bridge import (
    ExecutionBridgeLogError,
    log_execution_bridge,
)

logger = logging.getLogger(__name__)

__all__ = [
    "recalibrate",
    "bridge_log",
    "ExecutionEvidenceError",
    "ExecutionBridgeLogError",
]

DEFAULT_OUTPUT_PATH = Path("config/execution_model.calib.yaml")


class ExecutionEvidenceError(RuntimeError):
    """Raised when execution recalibration evidence cannot be produced."""


def _current_time() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float)) or value is None or value is True or value is False


def _format_scalar(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _dump_yaml(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, Mapping):
        lines: list[str] = []
        for key, item in value.items():
            if _is_scalar(item):
                lines.append(f"{prefix}{key}: {_format_scalar(item)}")
            else:
                lines.append(f"{prefix}{key}:")
                lines.append(_dump_yaml(item, indent + 2))
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if _is_scalar(item):
                lines.append(f"{prefix}- {_format_scalar(item)}")
            else:
                lines.append(f"{prefix}-")
                lines.append(_dump_yaml(item, indent + 2))
        return "\n".join(lines)
    return f"{prefix}{_format_scalar(value)}"


def _write_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_yaml(payload) + "\n", encoding="utf-8")


def recalibrate(
    *,
    source: Path,
    window: str,
    output: Path | None = None,
    dry_run: bool = False,
    strict: bool = False,
) -> Mapping[str, Any]:
    """Generate a mock calibration bundle for the execution model."""

    if not source.exists():
        message = f"Input parquet file not found: {source}"
        logger.error("execution.recalibrate.source_missing", extra={"source": str(source)})
        raise ExecutionEvidenceError(message)

    timestamp = _current_time()
    target_path = output or DEFAULT_OUTPUT_PATH

    payload: MutableMapping[str, Any] = {
        "status": "dry_run" if dry_run else "ok",
        "source": str(source),
        "window": window,
        "output": str(target_path),
        "strict": strict,
        "generated_at": timestamp.isoformat(),
        "summary": {
            "sample_count": 240,
            "latency_ms": {"p50": 128, "p90": 236, "p99": 415},
            "slippage_bps": {"mean": 1.8, "stdev": 0.6},
        },
    }

    if dry_run:
        logger.info("execution.recalibrate.dry_run", extra=payload)
        return payload

    evidence_document = {
        "metadata": {
            "command": "tradectl execution recalibrate",
            "generated_at": timestamp.isoformat(),
            "source": str(source),
            "window": window,
            "strict": strict,
            "mode": "mock",
        },
        "calibration": {
            "latency_model": {
                "distribution_ms": {
                    "p50": 128,
                    "p90": 236,
                    "p99": 415,
                },
                "recommended_guard_ms": 450,
            },
            "slippage_model": {
                "mean_bps": 1.8,
                "stdev_bps": 0.6,
                "percentiles_bps": {
                    "p50": 1.6,
                    "p90": 2.9,
                    "p99": 5.2,
                },
            },
            "sample_count": 240,
            "notes": [
                "Mock calibration generated for audit scaffolding.",
                "Replace with real aggregation when ExecutionModel hooks are available.",
            ],
        },
    }

    try:
        _write_yaml(target_path, evidence_document)
    except OSError as exc:
        logger.exception("execution.recalibrate.write_failed", extra={"output": str(target_path)})
        raise ExecutionEvidenceError(f"Failed to write calibration output: {target_path}") from exc

    logger.info("execution.recalibrate.completed", extra=payload)
    return payload


def bridge_log(
    *,
    mode: str,
    broker: str,
    stage: str,
    session_id: str,
    latency_ms: float,
    error_rate: float,
    decision: str,
    notes: str | None = None,
    metrics_path: Path = DEFAULT_EXECUTION_BRIDGE_METRICS,
    report_dir: Path = DEFAULT_EXECUTION_REPORT_DIR,
    report_date: date | None = None,
) -> Mapping[str, Any]:
    """Log execution bridge metrics and StageGuard exercise notes."""

    try:
        record = log_execution_bridge(
            mode=mode,
            broker=broker,
            stage=stage,
            session_id=session_id,
            latency_ms=latency_ms,
            error_rate=error_rate,
            decision=decision,
            notes=notes,
            metrics_path=metrics_path,
            report_dir=report_dir,
            report_date=report_date,
        )
    except ExecutionBridgeLogError as exc:
        raise ExecutionBridgeLogError(str(exc)) from exc

    payload: MutableMapping[str, Any] = record.to_mapping()
    payload["status"] = "ok"
    logger.info(
        "execution.bridge.logged",
        extra={"mode": mode, "stage": stage, "broker": broker, "metrics": str(metrics_path)},
    )
    return payload
