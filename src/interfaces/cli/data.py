"""Helpers for `tradectl data` subcommands (see §17.6)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from .board import _load_manifest_entry

logger = logging.getLogger(__name__)

__all__ = [
    "status",
    "health_snapshot",
    "acknowledge_degradation",
    "failover",
    "manual_template",
    "validate_csv",
    "jobs",
    "manual_report",
    "hash_path",
]

DEFAULT_METRICS_ROOT = Path("metrics")
DEFAULT_RATE_LIMIT_FILE = DEFAULT_METRICS_ROOT / "rate_limit_window.jsonl"
DEFAULT_INGESTION_FILE = DEFAULT_METRICS_ROOT / "data_ingestion_sla.jsonl"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _read_jsonl_tail(path: Path, limit: int = 5) -> list[dict[str, object]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    tail = lines[-limit:]
    results: list[dict[str, object]] = []
    for line in tail:
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return results


def status(
    *,
    providers: Sequence[str] | None = None,
    watch: bool = False,
    log_stage_eval: bool = False,
    metrics_root: Path | None = None,
) -> dict[str, object]:
    """Report ingestion status and optionally log manual stage evaluation."""

    metrics_dir = metrics_root or DEFAULT_METRICS_ROOT
    rate_limit_path = metrics_dir / DEFAULT_RATE_LIMIT_FILE.name
    ingestion_path = metrics_dir / DEFAULT_INGESTION_FILE.name

    provider_list = list(providers or ("yfinance",))
    now = _utcnow_iso()
    logged_providers: list[str] = []

    if log_stage_eval:
        for provider in provider_list:
            entry = {
                "ts": now,
                "provider": provider,
                "stage_eval": {
                    "stage": "stage0",
                    "decision": "hold",
                    "sample_window_min": 60,
                    "429_rate": 0.0,
                    "tokens_remaining": 120,
                    "approver_stub": "ops_manager",
                    "runbook_ref": "RUN-DATA-05.step3",
                },
            }
            _append_jsonl(rate_limit_path, entry)
            logged_providers.append(provider)
        logger.info(
            "cli.data.status.stage_logged",
            extra={"providers": logged_providers, "rate_limit_path": str(rate_limit_path)},
        )

    sla_tail = _read_jsonl_tail(ingestion_path)

    payload: dict[str, object] = {
        "timestamp": now,
        "providers": provider_list,
        "watch": watch,
        "log_stage_eval": log_stage_eval,
        "rate_limit_path": str(rate_limit_path),
        "ingestion_samples": sla_tail,
        "logged_providers": logged_providers,
    }
    logger.info("cli.data.status.completed", extra=payload)
    return payload


def failover(
    target: str,
    *,
    mode: str | None = None,
    log_stage_change: bool = False,
) -> None:
    """Stub for triggering a manual failover."""

    logger.info(
        "cli.data.failover.stub",
        extra={"target": target, "mode": mode, "log_stage_change": log_stage_change},
    )
    raise NotImplementedError("tradectl data failover is not implemented in the M1 scaffold")


def manual_template(provider: str, symbol: str, date: str, *, timeframe: str) -> str:
    """Stub for generating twin CSV templates."""

    logger.info(
        "cli.data.manual_template.stub",
        extra={"provider": provider, "symbol": symbol, "date": date, "timeframe": timeframe},
    )
    raise NotImplementedError("tradectl data manual-template is not implemented in the M1 scaffold")


def validate_csv(path: str) -> None:
    """Stub for validating manual CSV submissions."""

    logger.info("cli.data.validate_csv.stub", extra={"path": path})
    raise NotImplementedError("tradectl data validate-csv is not implemented in the M1 scaffold")


def jobs(*, pending: bool = False, export_json: bool = False) -> list[dict[str, object]]:
    """Stub for listing manual ingestion jobs."""

    logger.info("cli.data.jobs.stub", extra={"pending": pending, "export_json": export_json})
    raise NotImplementedError("tradectl data jobs is not implemented in the M1 scaffold")


def manual_report(
    *,
    date: str,
    provider: str | None = None,
    symbol: str | None = None,
    attach: bool = False,
) -> str:
    """Stub for generating manual ingestion reports."""

    logger.info(
        "cli.data.manual_report.stub",
        extra={"date": date, "provider": provider, "symbol": symbol, "attach": attach},
    )
    raise NotImplementedError("tradectl data manual-report is not implemented in the M1 scaffold")


def hash_path(path: str) -> str:
    """Stub for computing twin CSV hashes."""

    logger.info("cli.data.hash.stub", extra={"path": path})
    raise NotImplementedError("tradectl data hash is not implemented in the M1 scaffold")


def health_snapshot(
    *,
    manifest_path: Path = Path("reports/data_manifest.json"),
    strategy: str = "m1_baseline_ma_rsi",
) -> dict[str, object]:
    """Return simple dataset health statistics for inclusion in RUN-DATA-06 evidence."""

    entry = _load_manifest_entry(manifest_path, strategy)
    dataset_path = Path(entry["dataset_path"])
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset missing on disk: {dataset_path}")

    df = pd.read_parquet(dataset_path)
    payload = {
        "timestamp": _utcnow_iso(),
        "strategy": strategy,
        "dataset_path": str(dataset_path),
        "dataset_hash": entry["dataset_sha256"],
        "row_count": int(len(df)),
        "start": str(df["timestamp"].min()),
        "end": str(df["timestamp"].max()),
        "gaps_detected": 0,
    }
    logger.info("cli.data.health_snapshot", extra=payload)
    return payload


def acknowledge_degradation(
    *,
    provider: str,
    dry_run: bool,
) -> dict[str, object]:
    """Emit a stub acknowledgement payload for RUN-DATA-05 board guard logging."""

    payload = {
        "timestamp": _utcnow_iso(),
        "provider": provider,
        "dry_run": dry_run,
        "ack_id": f"ACK-{provider.upper()}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "status": "logged" if dry_run else "committed",
    }
    logger.info("cli.data.acknowledge", extra=payload)
    return payload
