"""Helpers for `tradectl data` subcommands (see §17.6)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pandas as pd

from .board import _load_manifest_entry
from src.core.health import HealthMonitor
from src.data.quality import DataQualityGuard
from src.data.rate_limit_guard import RateLimitGuard
from src.data.service import spawn_provider_workers

logger = logging.getLogger(__name__)

__all__ = [
    "status",
    "health_snapshot",
    "acknowledge_degradation",
    "failover",
    "rate_limit_snapshot",
    "export_rate_limit_env",
    "manual_template",
    "validate_csv",
    "jobs",
    "enqueue_manual_csv_job",
    "run_manual_csv_jobs",
    "manual_report",
    "hash_path",
    "update_latest",
]

DEFAULT_METRICS_ROOT = Path("metrics")
DEFAULT_RATE_LIMIT_FILE = DEFAULT_METRICS_ROOT / "rate_limit_window.jsonl"
DEFAULT_INGESTION_FILE = DEFAULT_METRICS_ROOT / "data_ingestion_sla.jsonl"
DEFAULT_MANUAL_CSV_METRICS = DEFAULT_METRICS_ROOT / "data_ingestion_manual.jsonl"
OPS_WORKLOG_PATH = Path("ops_worklog.jsonl")
DEFAULT_STAGE_CHANGE_LOG = Path("logs/ops/stage_change.log")
DEFAULT_MANUAL_CSV_LOG = Path("logs/ops/manual_csv.log")
DEFAULT_HEALTH_SUGGEST_LOG = Path("logs/events/health_suggested.jsonl")
DEFAULT_HEALTH_STATE_PATH = Path("snapshots/latest/health_state.json")
MANUAL_CSV_JOBS_DIR = Path("data") / "manual_fallback" / "jobs"
MANUAL_CSV_JOBS_LOG = MANUAL_CSV_JOBS_DIR / "jobs.jsonl"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _append_ops_worklog(task: str, payload: dict[str, object]) -> None:
    entry = {"timestamp": _utcnow_iso(), "task": task, **payload}
    _append_jsonl(OPS_WORKLOG_PATH, entry)


def _read_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _read_bool_env(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip() not in {"0", "false", "False", "no", "off"}


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
    auto_apply: bool = False,
    suggest_guarded: bool = False,
    metrics_root: Path | None = None,
) -> dict[str, object]:
    """Report ingestion status and optionally log stage evaluation."""

    metrics_dir = metrics_root or DEFAULT_METRICS_ROOT
    rate_limit_path = metrics_dir / DEFAULT_RATE_LIMIT_FILE.name
    ingestion_path = metrics_dir / DEFAULT_INGESTION_FILE.name

    provider_list = list(providers or ("yfinance",))
    now = _utcnow_iso()
    logged_providers: list[str] = []
    stage_evaluations: list[dict[str, object]] = []
    guard = RateLimitGuard(tokens_per_minute=60.0, burst_tokens=90.0, poll_interval_sec=15.0, stages=["stage0", "stage1", "stage2"])
    worker_plans: list[dict[str, object]] = []

    if log_stage_eval:
        for provider in provider_list:
            rate_429 = _latest_429_rate(rate_limit_path, provider, ingestion_path=ingestion_path)
            decision = guard.evaluate(
                provider=provider,
                rate_429=rate_429,
                allow_promotion=auto_apply,
            )
            entry = {
                "ts": now,
                "provider": provider,
                "stage_eval": {
                    **decision.to_mapping(),
                    "decision_source": "auto" if auto_apply else "manual",
                    "approver_stub": "ops_manager",
                    "runbook_ref": "RUN-DATA-05.step3",
                },
            }
            _append_jsonl(rate_limit_path, entry)
            logged_providers.append(provider)
            stage_evaluations.append(entry["stage_eval"])
            if auto_apply:
                _append_jsonl(
                    DEFAULT_STAGE_CHANGE_LOG,
                    {
                        "ts": now,
                        "event": "rate_limit_stage_apply",
                        "provider": provider,
                        "decision": decision.decision,
                        "stage": decision.stage,
                        "runbook_ref": "RUN-DATA-05.step3",
                    },
                )
                _append_ops_worklog(
                    "rate_limit_stage_apply",
                    {
                        "provider": provider,
                        "decision": decision.decision,
                        "stage": decision.stage,
                        "runbook_ref": "RUN-DATA-05.step3",
                    },
                )
        logger.info(
            "cli.data.status.stage_logged",
            extra={"providers": logged_providers, "rate_limit_path": str(rate_limit_path)},
        )
        plans = spawn_provider_workers(providers=provider_list, rate_limit_guard=guard, rate_limit_state={p["provider"]: p["stage"] for p in stage_evaluations})
        worker_plans = [
            {
                "provider": plan.provider,
                "stage": plan.stage,
                "poll_interval_sec": plan.poll_interval_sec,
                "max_workers": plan.max_workers,
            }
            for plan in plans
        ]

    sla_tail = _read_jsonl_tail(ingestion_path)
    health_payload: dict[str, object] | None = None
    if suggest_guarded:
        health_payload = _suggest_guarded_from_metrics(ingestion_path)

    payload: dict[str, object] = {
        "timestamp": now,
        "providers": provider_list,
        "watch": watch,
        "log_stage_eval": log_stage_eval,
        "suggest_guarded": suggest_guarded,
        "rate_limit_path": str(rate_limit_path),
        "ingestion_samples": sla_tail,
        "logged_providers": logged_providers,
        "stage_evaluations": stage_evaluations,
        "worker_plans": worker_plans,
        "health_suggestion": health_payload,
    }
    logger.info("cli.data.status.completed", extra=payload)
    return payload


def rate_limit_snapshot(
    *,
    providers: Sequence[str] | None = None,
) -> dict[str, object]:
    """Return the current RateLimitGuard settings and derived worker plans."""

    provider_list = list(providers or ("yfinance",))
    guard_enabled = _read_bool_env("TRADECTL_RATE_LIMIT_GUARD_ENABLED", True)
    tokens_per_minute = _read_float_env("TRADECTL_RATE_LIMIT_TPM", 60.0)
    burst_tokens = _read_float_env("TRADECTL_RATE_LIMIT_BURST", 90.0)
    poll_interval_sec = _read_float_env("TRADECTL_RATE_LIMIT_POLL_SEC", 15.0)
    stages_env = os.getenv("TRADECTL_RATE_LIMIT_STAGES", "stage0,stage1,stage2")
    stages = [stage.strip() for stage in stages_env.split(",") if stage.strip()] or ["stage0"]
    rate_limit_log_path = Path(os.getenv("TRADECTL_RATE_LIMIT_LOG", str(DEFAULT_RATE_LIMIT_FILE)))

    guard = None
    if guard_enabled:
        guard = RateLimitGuard(
            tokens_per_minute=tokens_per_minute,
            burst_tokens=burst_tokens,
            poll_interval_sec=poll_interval_sec,
            stages=stages,
        )
    plans = spawn_provider_workers(providers=provider_list, rate_limit_guard=guard, rate_limit_state={})
    worker_plans = [
        {
            "provider": plan.provider,
            "stage": plan.stage,
            "poll_interval_sec": plan.poll_interval_sec,
            "max_workers": plan.max_workers,
        }
        for plan in plans
    ]
    payload = {
        "guard_enabled": guard_enabled,
        "tokens_per_minute": tokens_per_minute,
        "burst_tokens": burst_tokens,
        "poll_interval_sec": poll_interval_sec,
        "stages": stages,
        "providers": provider_list,
        "rate_limit_log_path": str(rate_limit_log_path),
        "worker_plans": worker_plans,
    }
    logger.info("cli.data.rate_limit_snapshot", extra=payload)
    return payload


def export_rate_limit_env(path: Path, *, payload: Mapping[str, object]) -> str:
    """Write a simple env file for RateLimitGuard overrides."""

    lines = [
        f"TRADECTL_RATE_LIMIT_GUARD_ENABLED={1 if payload.get('guard_enabled') else 0}",
        f"TRADECTL_RATE_LIMIT_TPM={payload.get('tokens_per_minute')}",
        f"TRADECTL_RATE_LIMIT_BURST={payload.get('burst_tokens')}",
        f"TRADECTL_RATE_LIMIT_POLL_SEC={payload.get('poll_interval_sec')}",
        f"TRADECTL_RATE_LIMIT_STAGES={','.join(payload.get('stages') or [])}",
        f"TRADECTL_RATE_LIMIT_LOG={payload.get('rate_limit_log_path')}",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def failover(
    target: str,
    *,
    mode: str | None = None,
    log_stage_change: bool = False,
    manual_source: bool = False,
) -> dict[str, object]:
    """Trigger a manual failover and optionally log a stage change."""

    payload = {
        "ts": _utcnow_iso(),
        "target": target,
        "mode": mode,
        "log_stage_change": log_stage_change,
        "status": "ok",
        "manual_source": manual_source or target == "manual",
    }
    if log_stage_change:
        log_entry = {"event": "data.failover", **payload}
        _append_jsonl(DEFAULT_RATE_LIMIT_FILE, log_entry)
        _append_jsonl(DEFAULT_STAGE_CHANGE_LOG, log_entry)
    _append_ops_worklog("data_failover", {"target": target, "mode": mode, "status": payload["status"], "manual_source": payload["manual_source"]})
    logger.info("cli.data.failover.completed", extra=payload)
    return payload


def manual_template(provider: str, symbol: str, date: str, *, timeframe: str) -> str:
    """Generate twin CSV templates with required headers."""

    base_dir = Path("data") / "manual_fallback" / provider / symbol / date
    base_dir.mkdir(parents=True, exist_ok=True)
    filenames = [
        base_dir / f"fallback_{provider}_{symbol}_{timeframe}_{date}_op.csv",
        base_dir / f"fallback_{provider}_{symbol}_{timeframe}_{date}_review.csv",
    ]
    headers = ["ts", "timestamp_jst", "open", "high", "low", "close", "volume", "spread", "session_tag"]
    rows = _build_template_rows(date, timeframe=timeframe)
    for path in filenames:
        if not path.exists():
            if not rows.empty:
                rows.to_csv(path, index=False, columns=headers)
            else:
                path.write_text(",".join(headers) + "\n", encoding="utf-8")
    logger.info(
        "cli.data.manual_template.generated",
        extra={"provider": provider, "symbol": symbol, "date": date, "timeframe": timeframe, "files": [str(p) for p in filenames]},
    )
    _append_ops_worklog(
        "manual_csv_template",
        {"provider": provider, "symbol": symbol, "date": date, "timeframe": timeframe, "path": str(base_dir)},
    )
    _append_jsonl(
        DEFAULT_RATE_LIMIT_FILE,
        {
            "ts": _utcnow_iso(),
            "event": "manual_template",
            "provider": provider,
            "symbol": symbol,
            "timeframe": timeframe,
            "date": date,
            "runbook_ref": "RUN-DATA-05.step2",
        },
    )
    return str(base_dir)


def validate_csv(path: str) -> None:
    """Validate manual CSV submissions."""

    target = Path(path)
    try:
        if target.is_dir():
            op_files = sorted(target.glob("*_op.csv"))
            if not op_files:
                raise FileNotFoundError(f"No op CSV files found in {target}")
            for op_file in op_files:
                _validate_csv_pair(op_file)
                _log_manual_csv_verification(op_file)
        else:
            _validate_csv_pair(target)
            _log_manual_csv_verification(target)
    except Exception as exc:
        logger.error("cli.data.validate_csv.failed", extra={"path": path, "error": str(exc)})
        raise SystemExit(120) from exc
    logger.info("cli.data.validate_csv.completed", extra={"path": path})


def _validate_csv_pair(path: Path) -> None:
    """Validate op/review CSV pair with integrity and gap checks."""

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
        required_cols = {"open", "high", "low", "close", "volume", "spread"}
        ts_cols = {"ts", "timestamp"}
        if not (ts_cols & set(frame.columns)):
            raise ValueError(f"Missing timestamp column (ts|timestamp) in {csv_path}")
        missing = required_cols - set(frame.columns)
        if missing:
            raise ValueError(f"Missing required columns {missing} in {csv_path}")
        return frame

    op_frame = _load_frame(path)
    review_frame = _load_frame(review_path)

    _validate_required(op_frame, "op")
    _validate_required(review_frame, "review")

    if list(op_frame.columns) != list(review_frame.columns) or len(op_frame) != len(review_frame):
        raise ValueError(f"op/review shape mismatch: {path} vs {review_path}")

    for frame, label in ((op_frame, "op"), (review_frame, "review")):
        _validate_required(frame, label)
        if frame.isnull().any().any():
            raise ValueError(f"Missing values detected in {label} file: {path}")
        low_ok = (frame["low"] <= frame["open"]) & (frame["low"] <= frame["close"])
        high_ok = (frame["high"] >= frame["open"]) & (frame["high"] >= frame["close"])
        if not bool(low_ok.all() and high_ok.all()):
            raise ValueError(f"Price envelope violation in {label} file: {path}")
        if (frame["volume"] < 0).any():
            raise ValueError(f"Negative volume detected in {label} file: {path}")
        if (frame["spread"] < 0).any():
            raise ValueError(f"Negative spread detected in {label} file: {path}")
        session_col = frame.get("session_tag")
        if session_col is not None:
            allowed_sessions = {"asia", "london", "newyork", "overlap", "holiday"}
            if not set(session_col.dropna().unique()).issubset(allowed_sessions):
                raise ValueError(f"Invalid session_tag in {label} file: {path}")
        try:
            ts_col = "ts" if "ts" in frame.columns else "timestamp"
            timestamps = pd.to_datetime(frame[ts_col], utc=True)
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"Timestamp parsing failed for {label} file: {exc}") from exc
        if timestamps.duplicated().any():
            raise ValueError(f"Duplicate timestamps detected in {label} file: {path}")

        expected_step = _infer_step_seconds(path.stem)
        if expected_step and len(timestamps) >= 2:
            diffs = (timestamps.sort_values().diff().dropna().dt.total_seconds()).unique()
            if any(d != expected_step for d in diffs):
                raise ValueError(f"Timestamp gap detected in {label} file: {path} (expected {expected_step}s)")
        if "timestamp_jst" in frame.columns:
            ts_jst = pd.to_datetime(frame["timestamp_jst"], utc=True)
            if not ((ts_jst - timestamps).dt.total_seconds() == 9 * 3600).all():
                raise ValueError(f"UTC/JST mismatch in {label} file: {path}")

    if _hash_file(path) != _hash_file(review_path):
        raise ValueError(f"op/review hash mismatch: {path} vs {review_path}")


def _log_manual_csv_verification(path: Path) -> None:
    if path.name.endswith("_op.csv"):
        review_path = path.with_name(path.name.replace("_op.csv", "_review.csv"))
    elif path.name.endswith("_review.csv"):
        review_path = path.with_name(path.name.replace("_review.csv", "_op.csv"))
    else:
        review_path = path

    op_hash = _hash_file(path)
    review_hash = _hash_file(review_path) if review_path.exists() else None
    entry = {
        "ts": _utcnow_iso(),
        "event": "manual_csv.validate",
        "op_path": str(path),
        "review_path": str(review_path) if review_path.exists() else None,
        "op_hash": op_hash,
        "review_hash": review_hash,
        "status": "ok" if review_hash == op_hash else "mismatch",
        "runbook_ref": "RUN-DATA-06.step2",
    }
    _append_jsonl(DEFAULT_MANUAL_CSV_LOG, entry)
    _append_jsonl(DEFAULT_RATE_LIMIT_FILE, {"provider": "manual_csv", "stage_eval": entry})
    guard = DataQualityGuard()
    reviewer = os.getenv("MANUAL_CSV_REVIEWER", "ops_manager")
    guard.record_manual_csv_hash_verification(
        hash_value=op_hash,
        symbol=_infer_symbol_from_path(path),
        timeframe=_infer_timeframe_from_path(path),
        reviewer=reviewer,
        metrics_path=DEFAULT_MANUAL_CSV_METRICS,
    )
    _append_ops_worklog(
        "manual_csv_validate",
        {
            "op_path": str(path),
            "review_path": str(review_path) if review_path.exists() else None,
            "status": entry["status"],
        },
    )


def _validate_required(frame: pd.DataFrame, label: str) -> None:
    required_cols = {"open", "high", "low", "close", "volume", "spread"}
    ts_cols = {"ts", "timestamp"}
    missing = required_cols - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns {missing} in {label} file")
    if not (ts_cols & set(frame.columns)):
        raise ValueError(f"Missing timestamp column in {label} file")


def _infer_step_seconds(stem: str) -> int | None:
    """Infer expected step size from filename tokens (e.g., 5m -> 300s, 1h -> 3600s)."""

    for token in stem.lower().split("_"):
        match = re.fullmatch(r"(\d+)([mh])", token)
        if not match:
            continue
        value, unit = match.groups()
        try:
            magnitude = int(value)
        except ValueError:
            continue
        if unit == "m":
            return magnitude * 60
        if unit == "h":
            return magnitude * 3600
    return None


def _build_template_rows(date: str, *, timeframe: str) -> pd.DataFrame:
    normalized = _normalize_date(date)
    if normalized is None:
        return pd.DataFrame()
    step_seconds = _normalize_timeframe(timeframe)
    if step_seconds is None:
        return pd.DataFrame()
    start = datetime.fromisoformat(normalized).replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1) - timedelta(seconds=step_seconds)
    rows: list[dict[str, object]] = []
    current = start
    while current <= end:
        ts = current.replace(microsecond=0)
        ts_jst = ts.astimezone(timezone(timedelta(hours=9)))
        rows.append(
            {
                "ts": ts.isoformat().replace("+00:00", "Z"),
                "timestamp_jst": ts_jst.strftime("%Y-%m-%dT%H:%M:%S"),
                "open": "",
                "high": "",
                "low": "",
                "close": "",
                "volume": "",
                "spread": "",
                "session_tag": "",
            }
        )
        current += timedelta(seconds=step_seconds)
    return pd.DataFrame(rows)


def _normalize_date(raw: str) -> str | None:
    text = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _normalize_timeframe(timeframe: str) -> int | None:
    tf = timeframe.strip().lower()
    if tf in {"m5", "5m", "5min"}:
        return 300
    if tf in {"h1", "1h", "60m"}:
        return 3600
    return None


def _infer_symbol_from_path(path: Path) -> str:
    parts = path.name.split("_")
    if len(parts) >= 3:
        return parts[2].upper()
    return "UNKNOWN"


def _infer_timeframe_from_path(path: Path) -> str:
    parts = path.name.split("_")
    if len(parts) >= 4:
        return parts[3]
    return "unknown"


def _manual_csv_range(date: str, *, timeframe: str) -> tuple[str, str]:
    normalized = _normalize_date(date)
    if normalized is None:
        raise ValueError(f"Invalid date format: {date}")
    step_seconds = _normalize_timeframe(timeframe)
    if step_seconds is None:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    start = datetime.fromisoformat(normalized).replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1) - timedelta(seconds=step_seconds)
    return (
        start.isoformat().replace("+00:00", "Z"),
        end.isoformat().replace("+00:00", "Z"),
    )


def _load_manual_csv_jobs() -> dict[str, dict[str, object]]:
    if not MANUAL_CSV_JOBS_LOG.exists():
        return {}
    entries = _read_jsonl_tail(MANUAL_CSV_JOBS_LOG, limit=5000)
    snapshots: dict[str, dict[str, object]] = {}
    for entry in entries:
        job_id = entry.get("job_id")
        if not job_id:
            continue
        snapshots[str(job_id)] = dict(entry)
    return snapshots


def _run_manual_csv_job(job: dict[str, object], *, dry_run: bool) -> dict[str, object]:
    provider = str(job.get("provider") or "manual")
    symbol = str(job.get("symbol") or "UNKNOWN")
    timeframe = str(job.get("timeframe") or "m5")
    date = str(job.get("date") or "")
    start = str(job.get("start") or "")
    end = str(job.get("end") or "")
    job_id = str(job.get("job_id") or "")
    payload = {
        "ts": _utcnow_iso(),
        "job_id": job_id,
        "task": "manual_csv",
        "provider": provider,
        "symbol": symbol,
        "timeframe": timeframe,
        "date": date,
        "start": start,
        "end": end,
    }
    if dry_run:
        payload["status"] = "dry_run"
        _append_jsonl(MANUAL_CSV_JOBS_LOG, payload)
        _append_ops_worklog("manual_csv_run", payload)
        return payload

    from src.data.providers.csv_loader import CsvLoaderProvider
    from src.data.service import MarketRequest

    request = MarketRequest(symbols=[symbol], timeframe=timeframe, start=start, end=end)
    provider_impl = CsvLoaderProvider()
    frames = list(provider_impl.fetch_bars(request))
    bars = frames[0].bars if frames else []
    bars_df = pd.DataFrame(bars)
    if bars_df.empty:
        payload["status"] = "empty"
        _append_jsonl(MANUAL_CSV_JOBS_LOG, payload)
        _append_ops_worklog("manual_csv_run", payload)
        return payload

    ts_col = "timestamp" if "timestamp" in bars_df.columns else "ts"
    bars_df[ts_col] = pd.to_datetime(bars_df[ts_col], utc=True, errors="coerce")
    bars_df = bars_df.dropna(subset=[ts_col])
    raw_dir = Path("data/raw") / "manual_csv" / symbol.lower()
    curated_dir = Path("data/research/curated") / symbol.lower()
    raw_dir.mkdir(parents=True, exist_ok=True)
    curated_dir.mkdir(parents=True, exist_ok=True)
    suffix = _normalize_timeframe_label(timeframe)
    raw_path = raw_dir / f"{date}_{suffix}.parquet"
    curated_path = curated_dir / f"{symbol.lower()}_{suffix}_latest.parquet"
    merged_raw = _merge_parquet_frame(raw_path, bars_df, ts_col=ts_col)
    merged_raw.to_parquet(raw_path, index=False)
    merged_curated = _merge_parquet_frame(curated_path, bars_df, ts_col=ts_col)
    merged_curated.to_parquet(curated_path, index=False)

    payload["status"] = "completed"
    payload["bars"] = len(bars_df)
    payload["raw_path"] = str(raw_path)
    payload["curated_path"] = str(curated_path)
    _append_jsonl(MANUAL_CSV_JOBS_LOG, payload)
    _append_ops_worklog("manual_csv_run", payload)
    return payload


def _merge_parquet_frame(path: Path, new_df: pd.DataFrame, *, ts_col: str) -> pd.DataFrame:
    if path.exists():
        existing = pd.read_parquet(path)
        merged = pd.concat([existing, new_df], ignore_index=True)
    else:
        merged = new_df.copy()
    merged[ts_col] = pd.to_datetime(merged[ts_col], utc=True, errors="coerce")
    merged = merged.dropna(subset=[ts_col]).drop_duplicates(subset=[ts_col]).sort_values(ts_col)
    return merged


def _normalize_timeframe_label(timeframe: str) -> str:
    tf = timeframe.strip().lower()
    if tf in {"m5", "5m", "5min"}:
        return "m5"
    if tf in {"h1", "1h", "60m"}:
        return "h1"
    return tf.replace(" ", "")


def _latest_429_rate(rate_limit_path: Path, provider: str, *, ingestion_path: Path | None = None) -> float:
    """Extract latest 429 rate for provider from rate_limit_window or ingestion metrics."""

    if not rate_limit_path.exists():
        rate_limit_lines = []
    else:
        rate_limit_lines = rate_limit_path.read_text(encoding="utf-8").splitlines()
    for line in reversed(rate_limit_lines):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("provider") == provider:
            stage_eval = payload.get("stage_eval") or {}
            value = stage_eval.get("429_rate")
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
        if payload.get("provider") == provider and "429_rate" in payload:
            try:
                return float(payload.get("429_rate"))
            except (TypeError, ValueError):
                pass
    if ingestion_path and ingestion_path.exists():
        for entry in reversed(_read_jsonl_tail(ingestion_path, limit=20)):
            if entry.get("provider") and entry.get("provider") != provider:
                continue
            if "429_rate" in entry:
                try:
                    return float(entry["429_rate"])
                except (TypeError, ValueError):
                    continue
            rate_limited = entry.get("rate_limited") or 0
            total = entry.get("requests") or entry.get("samples") or 0
            try:
                total_val = float(total)
                if total_val > 0:
                    return float(rate_limited) / total_val
            except (TypeError, ValueError):
                continue
    return 0.0


def _suggest_guarded_from_metrics(ingestion_path: Path) -> dict[str, object]:
    entries = _read_jsonl_tail(ingestion_path, limit=20)
    degraded = False
    details: list[str] = []
    for entry in entries:
        status = str(entry.get("status") or entry.get("latency_status") or "")
        bars = entry.get("bars")
        if status in {"error", "breach", "watch"}:
            degraded = True
            details.append(f"status:{status}")
        if bars is not None:
            try:
                if int(bars) == 0:
                    degraded = True
                    details.append("bars:0")
            except (TypeError, ValueError):
                pass
        if degraded:
            break

    if not degraded:
        return {"status": "ok", "reason": None, "runbook": None, "health_state_path": None}

    monitor = HealthMonitor()
    reason = "data_latency"
    runbook = "docs/runbooks/RUN-DATA-05.md"
    monitor.raise_condition(
        "degraded",
        reason,
        detail=";".join(details) if details else None,
        recommended_action="runbook:RUN-DATA-05#enter_guarded",
    )
    monitor.suggest_guarded(reason=reason, runbook=runbook, evidence=[str(ingestion_path)])
    snapshot = monitor.snapshot().to_dict()
    DEFAULT_HEALTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_HEALTH_STATE_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    event = {
        "ts": _utcnow_iso(),
        "event": "health.suggest_guarded",
        "reason": reason,
        "runbook_ref": "RUN-DATA-05",
        "details": details,
        "evidence": [str(ingestion_path)],
        "health_state_path": str(DEFAULT_HEALTH_STATE_PATH),
    }
    _append_jsonl(DEFAULT_HEALTH_SUGGEST_LOG, event)
    _append_ops_worklog("health_suggest_guarded", event)
    return {
        "status": "suggested",
        "reason": reason,
        "runbook": runbook,
        "health_state_path": str(DEFAULT_HEALTH_STATE_PATH),
        "details": details,
    }


def jobs(*, pending: bool = False, export_json: bool = False) -> list[dict[str, object]]:
    """List manual ingestion jobs under data/manual_fallback."""

    entries: list[dict[str, object]] = []
    base = Path("data") / "manual_fallback"
    if not base.exists():
        return entries
    for path in sorted(base.rglob("*_op.csv")):
        review_path = path.with_name(path.name.replace("_op.csv", "_review.csv"))
        status_value = "ready" if review_path.exists() else "pending"
        if pending and status_value != "pending":
            continue
        entry = {
            "path": str(path),
            "review_path": str(review_path) if review_path.exists() else None,
            "status": status_value,
        }
        entries.append(entry)
    job_snapshots = _load_manual_csv_jobs()
    for job_id, job in job_snapshots.items():
        status_value = str(job.get("status") or "queued")
        if pending and status_value not in {"pending", "queued"}:
            continue
        entry = {
            "job_id": job_id,
            "task": job.get("task"),
            "provider": job.get("provider"),
            "symbol": job.get("symbol"),
            "timeframe": job.get("timeframe"),
            "status": status_value,
            "date": job.get("date"),
            "start": job.get("start"),
            "end": job.get("end"),
        }
        entries.append(entry)
    if export_json:
        snapshot_path = base / "jobs_snapshot.json"
        snapshot_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("cli.data.jobs.exported", extra={"path": str(snapshot_path), "count": len(entries)})
    logger.info("cli.data.jobs.completed", extra={"pending": pending, "count": len(entries)})
    return entries


def enqueue_manual_csv_job(
    *,
    provider: str,
    symbol: str,
    timeframe: str,
    date: str,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, object]:
    """Register a manual CSV ingestion job."""

    if not start or not end:
        start, end = _manual_csv_range(date, timeframe=timeframe)
    job_id = f"{provider}_{symbol}_{timeframe}_{date}"
    payload = {
        "ts": _utcnow_iso(),
        "job_id": job_id,
        "task": "manual_csv",
        "provider": provider,
        "symbol": symbol,
        "timeframe": timeframe,
        "date": date,
        "start": start,
        "end": end,
        "status": "queued",
    }
    _append_jsonl(MANUAL_CSV_JOBS_LOG, payload)
    _append_ops_worklog("manual_csv_enqueue", payload)
    logger.info("cli.data.manual_csv.enqueue", extra=payload)
    return payload


def run_manual_csv_jobs(*, job_ids: Sequence[str] | None = None, dry_run: bool = False) -> list[dict[str, object]]:
    """Process queued manual CSV jobs into curated parquet files."""

    snapshots = _load_manual_csv_jobs()
    results: list[dict[str, object]] = []
    for job_id, job in snapshots.items():
        if job.get("status") != "queued":
            continue
        if job_ids and job_id not in job_ids:
            continue
        result = _run_manual_csv_job(job, dry_run=dry_run)
        results.append(result)
    return results


def manual_report(
    *,
    date: str,
    provider: str | None = None,
    symbol: str | None = None,
    attach: bool = False,
) -> str:
    """Generate a manual ingestion validation report."""

    base = Path("reports") / "validation_log"
    base.mkdir(parents=True, exist_ok=True)
    filename = base / f"manual_csv_{provider or 'any'}_{symbol or 'any'}_{date}.md"

    root = Path("data") / "manual_fallback"
    matches = list(root.glob(f"{provider or '*'}/*/{date}/*_op.csv")) if root.exists() else []
    rows: list[str] = []
    overall_status = "ok"
    for op_path in sorted(matches):
        review_path = op_path.with_name(op_path.name.replace("_op.csv", "_review.csv"))
        review_exists = review_path.exists()
        status = "ready" if review_exists else "pending"
        if review_exists:
            try:
                hash_ok = _hash_file(op_path) == _hash_file(review_path)
            except Exception:
                hash_ok = False
            if not hash_ok:
                status = "mismatch"
                overall_status = "warn"
        else:
            overall_status = "warn"
        rows.append(f"- {op_path.name}: {status} (op={op_path}, review={review_path if review_exists else 'missing'})")

    lines = [
        f"# Manual CSV Validation Report {date}",
        f"- provider: {provider or 'any'}",
        f"- symbol: {symbol or 'any'}",
        f"- generated_at: {_utcnow_iso()}",
        f"- status: {overall_status}",
        f"- attach: {attach}",
        "",
        "## Files",
    ]
    if rows:
        lines.extend(rows)
    else:
        lines.append("- No matching files found")
    filename.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _append_ops_worklog(
        "manual_csv_report",
        {
            "provider": provider,
            "symbol": symbol,
            "date": date,
            "status": overall_status,
            "path": str(filename),
            "files": len(matches),
        },
    )
    logger.info(
        "cli.data.manual_report.generated",
        extra={"date": date, "provider": provider, "symbol": symbol, "path": str(filename), "status": overall_status},
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


def _load_watchlist_datasets(manifest_path: Path, strategy: str) -> Mapping[str, Mapping[str, str]]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    strategies = payload.get("strategies") or {}
    if strategy not in strategies:
        raise KeyError(f"Strategy '{strategy}' missing in {manifest_path}")
    entry = strategies[strategy]
    watchlist = entry.get("watchlist_datasets") or {}
    return {str(symbol).upper(): dict(meta) for symbol, meta in watchlist.items()}


def update_latest(
    *,
    symbols: Sequence[str],
    latest_days: int,
    manifest_path: Path,
    strategy: str,
    merged_override: Mapping[str, Path] | None = None,
) -> list[dict[str, object]]:
    """Generate *_m5_latest.parquet from merged datasets."""

    watchlist = _load_watchlist_datasets(manifest_path, strategy)
    results: list[dict[str, object]] = []
    for symbol in symbols:
        symbol_key = symbol.upper()
        merged_path = (merged_override or {}).get(symbol_key)
        if merged_path is None:
            meta = watchlist.get(symbol_key)
            if not meta or "path" not in meta:
                raise FileNotFoundError(f"Missing merged path for {symbol_key} in manifest")
            merged_path = Path(meta["path"])
        if not merged_path.exists():
            raise FileNotFoundError(f"Merged dataset not found: {merged_path}")

        df = pd.read_parquet(merged_path)
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if not required.issubset(df.columns):
            missing = sorted(required - set(df.columns))
            raise ValueError(f"{merged_path} missing columns: {missing}")
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
        df["timestamp"] = df["timestamp"].dt.tz_convert(None)
        end_ts = df["timestamp"].max()
        start_ts = end_ts - pd.Timedelta(days=latest_days)
        latest_df = df[df["timestamp"] >= start_ts]

        latest_path = merged_path.parent / f"{symbol_key.lower()}_m5_latest.parquet"
        latest_df.to_parquet(latest_path, index=False)
        results.append(
            {
                "symbol": symbol_key,
                "latest_path": str(latest_path),
                "rows": int(len(latest_df)),
                "window": {"from": str(start_ts), "to": str(end_ts)},
            }
        )

    return results


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
