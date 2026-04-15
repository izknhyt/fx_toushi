"""Signal log export helpers."""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SIGNAL_LOG_PATH = Path("logs") / "events" / "signal.generated.jsonl"
DEFAULT_EXPORT_DIR = Path("reports") / "exports"

PREFERRED_COLUMNS = [
    "ts",
    "event",
    "status",
    "reason",
    "strategy_id",
    "symbol",
    "direction",
    "level",
    "buffer",
    "breakout",
    "score",
    "confidence",
    "rationale",
    "badges",
    "watchlist",
    "feature_flags",
    "seed",
]

DEDUP_FIELDS = [
    "ts",
    "strategy_id",
    "symbol",
    "direction",
    "level",
    "score",
    "status",
]


def export_signals_csv(
    *,
    input_path: Path = DEFAULT_SIGNAL_LOG_PATH,
    output_path: Path | None = None,
    window_from: str | None = None,
    window_to: str | None = None,
    sort_by_ts: bool = True,
    append: bool = False,
    monthly: bool = False,
) -> dict[str, Any]:
    """Export signal logs to CSV with all observed columns."""

    if not input_path.exists():
        raise FileNotFoundError(f"Signal log not found: {input_path}")

    records = _load_jsonl(input_path)
    from_ts = _parse_iso(window_from) if window_from else None
    to_ts = _parse_iso(window_to) if window_to else None
    if from_ts or to_ts:
        records = [r for r in records if _within_window(r, from_ts, to_ts)]

    if sort_by_ts:
        records.sort(key=_sort_key)

    columns = _build_columns(records)
    if output_path is None:
        output_path = _default_output_path(monthly=monthly)

    output_path = _resolve_output_path(output_path, monthly=monthly)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    appended = 0
    skipped = 0
    if append:
        appended, skipped, columns = _append_csv(
            output_path=output_path,
            records=records,
            columns=columns,
        )
    else:
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for record in records:
                writer.writerow(_flatten_record(record, columns))
        appended = len(records)

    payload = {
        "input": str(input_path),
        "output": str(output_path),
        "rows": len(records),
        "appended": appended,
        "skipped_duplicates": skipped,
        "columns": columns,
        "window": {"from": window_from, "to": window_to},
        "sorted": sort_by_ts,
        "append": append,
        "monthly": monthly,
    }
    logger.info("signals.export_csv", extra=payload)
    return payload


def _default_output_path(*, monthly: bool = False) -> Path:
    if monthly:
        return _monthly_output_path()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    return DEFAULT_EXPORT_DIR / f"signal_generated_{stamp}.csv"


def _monthly_output_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m")
    return DEFAULT_EXPORT_DIR / f"signal_generated_{stamp}.csv"


def _resolve_output_path(output_path: Path, *, monthly: bool) -> Path:
    if output_path.suffix:
        return output_path
    if output_path.exists() and output_path.is_dir():
        return output_path / _monthly_output_path().name if monthly else output_path / _default_output_path().name
    if str(output_path).endswith("/"):
        base = output_path
        return base / _monthly_output_path().name if monthly else base / _default_output_path().name
    return output_path / _monthly_output_path().name if monthly else output_path / _default_output_path().name


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("signals.invalid_json", extra={"path": str(path)})
    return entries


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _record_ts(record: dict[str, Any]) -> datetime | None:
    ts = record.get("ts") or record.get("timestamp")
    if isinstance(ts, str):
        return _parse_iso(ts)
    return None


def _within_window(
    record: dict[str, Any],
    window_from: datetime | None,
    window_to: datetime | None,
) -> bool:
    ts = _record_ts(record)
    if ts is None:
        return False
    if window_from and ts < window_from:
        return False
    if window_to and ts > window_to:
        return False
    return True


def _sort_key(record: dict[str, Any]) -> tuple[int, datetime | None]:
    ts = _record_ts(record)
    if ts is None:
        return (1, None)
    return (0, ts)


def _build_columns(records: list[dict[str, Any]]) -> list[str]:
    keys: set[str] = set()
    for record in records:
        keys.update(record.keys())
    ordered: list[str] = []
    for key in PREFERRED_COLUMNS:
        if key in keys:
            ordered.append(key)
            keys.discard(key)
    ordered.extend(sorted(keys))
    return ordered


def _flatten_record(record: dict[str, Any], columns: list[str]) -> dict[str, str]:
    flattened: dict[str, str] = {}
    for key in columns:
        value = record.get(key)
        if value is None:
            flattened[key] = ""
        elif isinstance(value, (dict, list, tuple)):
            flattened[key] = json.dumps(value, ensure_ascii=False)
        else:
            flattened[key] = str(value)
    return flattened


def _append_csv(
    *,
    output_path: Path,
    records: list[dict[str, Any]],
    columns: list[str],
) -> tuple[int, int, list[str]]:
    existing_header: list[str] = []
    existing_keys: set[str] = set()
    if output_path.exists():
        with output_path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            existing_header = reader.fieldnames or []
            for row in reader:
                existing_keys.add(_dedup_key(row))

    merged_columns = _merge_columns(existing_header, columns)
    if output_path.exists() and merged_columns != existing_header:
        _rewrite_csv(output_path=output_path, columns=merged_columns)
    elif not output_path.exists():
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=merged_columns)
            writer.writeheader()

    appended = 0
    skipped = 0
    with output_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=merged_columns)
        for record in records:
            row = _flatten_record(record, merged_columns)
            key = _dedup_key(row)
            if key in existing_keys:
                skipped += 1
                continue
            existing_keys.add(key)
            writer.writerow(row)
            appended += 1
    return appended, skipped, merged_columns


def _merge_columns(existing: list[str], incoming: list[str]) -> list[str]:
    merged = list(existing)
    for key in incoming:
        if key not in merged:
            merged.append(key)
    return merged


def _rewrite_csv(*, output_path: Path, columns: list[str]) -> None:
    temp_path = output_path.with_suffix(".tmp")
    with output_path.open(encoding="utf-8", newline="") as handle, temp_path.open(
        "w", encoding="utf-8", newline=""
    ) as temp_handle:
        reader = csv.DictReader(handle)
        writer = csv.DictWriter(temp_handle, fieldnames=columns)
        writer.writeheader()
        for row in reader:
            writer.writerow(_flatten_record(row, columns))
    temp_path.replace(output_path)


def _dedup_key(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in DEDUP_FIELDS:
        value = row.get(field)
        if value is None:
            parts.append("")
        else:
            parts.append(str(value))
    return "|".join(parts)
