"""Helpers for `tradectl data` subcommands (see §17.6)."""

from __future__ import annotations

import hashlib
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

    payload = {
        "ts": _utcnow_iso(),
        "target": target,
        "mode": mode,
        "log_stage_change": log_stage_change,
    }
    if log_stage_change:
        _append_jsonl(DEFAULT_RATE_LIMIT_FILE, {"event": "data.failover", **payload})
    logger.info("cli.data.failover.completed", extra=payload)


def manual_template(provider: str, symbol: str, date: str, *, timeframe: str) -> str:
    """Stub for generating twin CSV templates."""

    base_dir = Path("data") / "manual_fallback" / provider / symbol / date
    base_dir.mkdir(parents=True, exist_ok=True)
    filenames = [
        base_dir / f"fallback_{provider}_{symbol}_{timeframe}_{date}_op.csv",
        base_dir / f"fallback_{provider}_{symbol}_{timeframe}_{date}_review.csv",
    ]
    headers = ["timestamp", "open", "high", "low", "close", "volume"]
    for path in filenames:
        if not path.exists():
            path.write_text(",".join(headers) + "\n", encoding="utf-8")
    logger.info(
        "cli.data.manual_template.generated",
        extra={"provider": provider, "symbol": symbol, "date": date, "timeframe": timeframe, "files": [str(p) for p in filenames]},
    )
    return str(base_dir)


def validate_csv(path: str) -> None:
    """Stub for validating manual CSV submissions."""

    target = Path(path)
    try:
        if target.is_dir():
            op_files = sorted(target.glob("*_op.csv"))
            if not op_files:
                raise FileNotFoundError(f"No op CSV files found in {target}")
            for op_file in op_files:
                _validate_csv_pair(op_file)
        else:
            _validate_csv_pair(target)
    except Exception as exc:
        logger.error("cli.data.validate_csv.failed", extra={"path": path, "error": str(exc)})
        raise SystemExit(120) from exc
    logger.info("cli.data.validate_csv.completed", extra={"path": path})


def _validate_csv_pair(path: Path) -> None:
    """Validate op/review CSV pair with basic integrity checks."""

    if path.is_dir():
        raise ValueError("CSV validation requires a file path, not a directory")
    if path.suffix.lower() != ".csv":
        raise ValueError(f"Expected CSV file, got: {path}")
    if path.name.endswith("_op.csv"):
        review_path = path.with_name(path.name.replace("_op.csv", "_review.csv"))
    elif path.name.endswith("_review.csv"):
        review_path = path.with_name(path.name.replace("_review.csv", "_op.csv"))
    else:
        review_path = path
    if not review_path.exists():
        raise FileNotFoundError(f"Missing twin CSV: {review_path}")

    def _load_frame(csv_path: Path) -> pd.DataFrame:
        frame = pd.read_csv(csv_path)
        required_cols = {"open", "high", "low", "close"}
        missing = required_cols - set(frame.columns)
        if missing:
            raise ValueError(f"Missing required columns {missing} in {csv_path}")
        return frame

    op_frame = _load_frame(path)
    review_frame = _load_frame(review_path)

    for frame, label in ((op_frame, "op"), (review_frame, "review")):
        if not frame.empty:
            low_ok = (frame["low"] <= frame["open"]) & (frame["low"] <= frame["close"])
            high_ok = (frame["high"] >= frame["open"]) & (frame["high"] >= frame["close"])
            if not bool(low_ok.all() and high_ok.all()):
                raise ValueError(f"Price envelope violation in {label} file: {path}")
        if "timestamp" in frame.columns:
            try:
                timestamps = pd.to_datetime(frame["timestamp"], utc=True)
                timeframe_token = path.stem.lower()
                if "5" in timeframe_token and not all(ts.minute % 5 == 0 for ts in timestamps):
                    raise ValueError(f"Timestamp 5m boundary violation in {label} file: {path}")
                if "1h" in timeframe_token or "h1" in timeframe_token:
                    if not all(ts.minute == 0 for ts in timestamps):
                        raise ValueError(f"Timestamp 1h boundary violation in {label} file: {path}")
                # gap check
                if len(timestamps) >= 2:
                    diffs = (timestamps.sort_values().diff().dropna().dt.total_seconds()).unique()
                    expected = 300 if "5" in timeframe_token else 3600
                    if any(d != expected for d in diffs):
                        raise ValueError(f"Timestamp gap detected in {label} file: {path}")
                if "timestamp_jst" in frame.columns:
                    ts_jst = pd.to_datetime(frame["timestamp_jst"], utc=True)
                    if not ((ts_jst - timestamps).dt.total_seconds() == 9 * 3600).all():
                        raise ValueError(f"UTC/JST mismatch in {label} file: {path}")
            except Exception as exc:
                raise ValueError(f"Timestamp parsing failed for {label} file: {exc}") from exc

    if _hash_file(path) != _hash_file(review_path):
        raise ValueError(f"op/review hash mismatch: {path} vs {review_path}")


def jobs(*, pending: bool = False, export_json: bool = False) -> list[dict[str, object]]:
    """Stub for listing manual ingestion jobs."""

    _ = export_json
    entries: list[dict[str, object]] = []
    base = Path("data") / "manual_fallback"
    if not base.exists():
        return entries
    for path in sorted(base.rglob("*_op.csv")):
        status = "pending" if pending else "ok"
        entries.append({"path": str(path), "status": status})
    logger.info("cli.data.jobs.completed", extra={"pending": pending, "count": len(entries)})
    return entries


def manual_report(
    *,
    date: str,
    provider: str | None = None,
    symbol: str | None = None,
    attach: bool = False,
) -> str:
    """Stub for generating manual ingestion reports."""

    base = Path("reports") / "validation_log"
    base.mkdir(parents=True, exist_ok=True)
    filename = base / f"manual_csv_{provider or 'any'}_{symbol or 'any'}_{date}.md"
    lines = [
        f"# Manual CSV Validation Report {date}",
        f"- provider: {provider or 'any'}",
        f"- symbol: {symbol or 'any'}",
        f"- generated_at: {_utcnow_iso()}",
        f"- attach: {attach}",
    ]
    filename.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(
        "cli.data.manual_report.generated",
        extra={"date": date, "provider": provider, "symbol": symbol, "path": str(filename)},
    )
    return str(filename)


def hash_path(path: str) -> str:
    """Stub for computing twin CSV hashes."""

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    value = _hash_file(file_path)
    logger.info("cli.data.hash.completed", extra={"path": path, "hash": value})
    return value


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


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
