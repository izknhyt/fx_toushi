"""Generic event stream helpers (directory scaffold, see §1.3)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = ["tail_events"]


def tail_events(
    *,
    since: str | None = None,
    follow: bool = False,
    log_dir: Path = Path("logs") / "events",
) -> list[dict[str, object]]:
    """Return event entries after ``since`` (follow is best-effort)."""

    since_dt = _parse_iso(since) if since else None
    entries: list[dict[str, object]] = []
    for path in sorted(log_dir.glob("*.jsonl")):
        entries.extend(_load_jsonl(path))
    filtered = [entry for entry in entries if _matches_since(entry, since_dt)]
    logger.info(
        "cli.events.tail",
        extra={"since": since, "follow": follow, "count": len(filtered), "log_dir": str(log_dir)},
    )
    return filtered


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
            logger.warning("cli.events.invalid_json", extra={"path": str(path)})
    return entries


def _matches_since(entry: dict[str, object], since_dt: datetime | None) -> bool:
    if since_dt is None:
        return True
    ts = _parse_iso(entry.get("ts") or entry.get("timestamp"))
    if ts is None:
        return False
    return ts >= since_dt


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
