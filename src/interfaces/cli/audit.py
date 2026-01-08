"""Audit log helpers for `tradectl audit` commands (see §17.13)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

__all__ = ["tail", "export"]


def tail(
    *,
    since: str,
    event: Iterable[str] | None = None,
    json_output: bool = False,
    log_dir: Path = Path("logs") / "audit",
) -> list[dict[str, object]]:
    """Return audit entries after ``since`` filtered by event name."""

    since_dt = _parse_iso(since)
    event_set = {str(item) for item in (event or []) if str(item)}
    entries: list[dict[str, object]] = []
    for path in sorted(log_dir.glob("*.jsonl")):
        entries.extend(_load_jsonl(path))
    filtered = [
        entry
        for entry in entries
        if _matches_since(entry, since_dt) and _matches_event(entry, event_set)
    ]
    logger.info(
        "cli.audit.tail",
        extra={
            "since": since,
            "event": list(event_set),
            "json": json_output,
            "count": len(filtered),
            "log_dir": str(log_dir),
        },
    )
    return filtered


def export(
    *,
    export_type: str,
    date_from: str,
    date_to: str,
    out: str,
    log_dir: Path = Path("logs") / "audit",
) -> str:
    """Export audit entries to JSONL within the date range."""

    start = _parse_iso(date_from)
    end = _parse_iso(date_to)
    if start is None or end is None:
        raise ValueError("date_from/date_to must be ISO8601 or YYYY-MM-DD strings")

    sources = _resolve_sources(log_dir, export_type)
    entries: list[dict[str, object]] = []
    for path in sources:
        entries.extend(_load_jsonl(path))
    filtered = [entry for entry in entries if _between(entry, start, end)]

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for entry in filtered:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")

    logger.info(
        "cli.audit.export",
        extra={
            "type": export_type,
            "from": date_from,
            "to": date_to,
            "out": out,
            "count": len(filtered),
        },
    )
    return str(out_path)


def _resolve_sources(log_dir: Path, export_type: str) -> list[Path]:
    token = export_type.strip()
    if not token or token.lower() == "all":
        return sorted(log_dir.glob("*.jsonl"))
    if token.endswith(".jsonl"):
        path = log_dir / token
    else:
        path = log_dir / f"{token}.jsonl"
    return [path] if path.exists() else []


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    entries: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("cli.audit.invalid_json", extra={"path": str(path)})
    return entries


def _matches_since(entry: dict[str, object], since_dt: datetime | None) -> bool:
    if since_dt is None:
        return True
    ts = _parse_iso(entry.get("ts") or entry.get("timestamp"))
    if ts is None:
        return False
    return ts >= since_dt


def _matches_event(entry: dict[str, object], event_set: set[str]) -> bool:
    if not event_set:
        return True
    event_name = entry.get("event") or entry.get("event_type")
    return isinstance(event_name, str) and event_name in event_set


def _between(entry: dict[str, object], start: datetime, end: datetime) -> bool:
    ts = _parse_iso(entry.get("ts") or entry.get("timestamp"))
    if ts is None:
        return False
    return start <= ts <= end


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
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
