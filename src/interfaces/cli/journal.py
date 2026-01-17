"""Trade journal CLI helpers."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from src.journal import JournalValidationError, TradeJournalService


def _parse_window(value: str) -> timedelta | None:
    if not value:
        return None
    token = value.strip().lower()
    unit = token[-1]
    try:
        amount = int(token[:-1])
    except ValueError:
        return None
    if unit == "s":
        return timedelta(seconds=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    if unit == "w":
        return timedelta(weeks=amount)
    return None


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _load_note(note: str | None, note_file: Path | None) -> str:
    if note_file is not None:
        return note_file.read_text(encoding="utf-8").strip()
    if note:
        return note
    return ""


def journal_list(
    *,
    service: TradeJournalService,
    week: str | None = None,
    strategy: str | None = None,
    regime: str | None = None,
    mode: str | None = None,
    board_mode: str | None = None,
) -> Mapping[str, object]:
    entries = service.list(
        week=week,
        strategy_id=strategy,
        regime=regime,
        mode=mode,
        board_mode=board_mode,
    )
    return {"status": "ok", "entries": entries, "count": len(entries)}


def journal_add_note(
    *,
    service: TradeJournalService,
    entry_id: str | None,
    ticket_id: str | None,
    author: str,
    note: str | None,
    note_file: Path | None,
    tags: list[str] | None,
) -> Mapping[str, object]:
    resolved_note = _load_note(note, note_file)
    if not resolved_note:
        raise JournalValidationError("note_md is required (--note or --note-file)")
    resolved_entry_id = entry_id
    if not resolved_entry_id and ticket_id:
        entry = service.get_entry_by_ticket(ticket_id=ticket_id)
        if entry:
            resolved_entry_id = entry.entry_id
    if not resolved_entry_id:
        raise JournalValidationError("entry_id or valid ticket_id is required")
    payload = service.add_note(
        entry_id=resolved_entry_id,
        author=author,
        note_md=resolved_note,
        tags=tags,
    )
    return {
        "status": "ok",
        "entry_id": resolved_entry_id,
        "note_id": payload.get("note_id"),
        "audit_log": str(service.audit_log_path),
    }


def journal_review(
    *,
    service: TradeJournalService,
    week: str,
    include_notes: bool,
    export_path: Path | None,
) -> Mapping[str, object]:
    summary = service.generate_weekly_summary(week)
    entries = service.list(week=week)
    lines = [f"# Trade Journal Review ({week})", ""]
    lines.append("## Summary")
    lines.append(json.dumps(summary, ensure_ascii=False, indent=2))
    lines.append("")
    lines.append("## Entries")
    if not entries:
        lines.append("- No entries")
    else:
        for entry in entries:
            ts = entry.get("created_ts") or entry.get("ts") or "unknown"
            ticket = entry.get("ticket_id") or "unknown"
            user = entry.get("approved_by") or entry.get("user") or "unknown"
            note = entry.get("note") or entry.get("decision") or ""
            line = f"- {ts} [{ticket}] {user}"
            if include_notes and note:
                line = f"{line}: {note}"
            lines.append(line)
    output = "\n".join(lines) + "\n"
    export = None
    if export_path is not None:
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(output, encoding="utf-8")
        export = str(export_path)
    return {"status": "ok", "week": week, "summary": summary, "export": export}


def journal_stats(
    *,
    service: TradeJournalService,
    window: str,
    group_by: str,
) -> Mapping[str, object]:
    allowed = {"strategy_id", "regime", "board_mode"}
    if group_by not in allowed:
        raise ValueError("group_by must be strategy_id, regime, or board_mode")
    window_td = _parse_window(window)
    if window_td is None:
        raise ValueError("window must be a duration like 90d/4w/24h")
    cutoff = datetime.now(timezone.utc) - window_td
    entries = service.list()
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for entry in entries:
        ts = _parse_ts(str(entry.get("created_ts") or entry.get("ts") or ""))
        if ts is None or ts < cutoff:
            continue
        key = str(entry.get(group_by) or "unknown")
        grouped[key].append(entry)
    stats: dict[str, dict[str, Any]] = {}
    for key, group in grouped.items():
        wins = 0
        total = 0
        slippage_values: list[float] = []
        for entry in group:
            actual_r = entry.get("actual_r")
            if isinstance(actual_r, (int, float)):
                total += 1
                if actual_r > 0:
                    wins += 1
            slippage = entry.get("slippage_pips")
            if isinstance(slippage, (int, float)):
                slippage_values.append(float(slippage))
        avg_slippage = sum(slippage_values) / len(slippage_values) if slippage_values else None
        stats[key] = {
            "entries": len(group),
            "win_rate": wins / total if total else None,
            "avg_slippage_pips": avg_slippage,
        }
    return {
        "status": "ok",
        "window": window,
        "group_by": group_by,
        "stats": stats,
    }
