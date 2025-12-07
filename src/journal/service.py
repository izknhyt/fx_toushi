"""Lightweight trade journal service placeholder."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping


@dataclass(slots=True)
class JournalEntry:
    """Single journal entry captured from approvals or manual notes."""

    ts: datetime
    ticket_id: str
    user: str
    note: str
    week: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["ts"] = self.ts.astimezone(timezone.utc).isoformat()
        return payload


class TradeJournalService:
    """Persist journal entries to a JSONL file."""

    def __init__(self, path: Path | str = "logs/journal/entries.jsonl") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: JournalEntry) -> JournalEntry:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.to_dict(), ensure_ascii=False))
            handle.write("\n")
        return entry

    def list(self, *, week: str | None = None) -> list[Mapping[str, object]]:
        if not self._path.exists():
            return []
        entries: list[Mapping[str, object]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if week and payload.get("week") != week:
                continue
            entries.append(payload)
        return entries

    def from_ticket_action(self, *, ticket_id: str, user: str, note: str, week: str | None = None) -> JournalEntry:
        return JournalEntry(ts=datetime.now(timezone.utc), ticket_id=ticket_id, user=user, note=note, week=week)

    def export_weekly(self, *, week: str, output_dir: Path | str = "reports/journal") -> Path:
        """Export a weekly journal summary to Markdown."""

        entries = self.list(week=week)
        lines = [f"# Trade Journal {week}", ""]
        if not entries:
            lines.append("- No entries")
        else:
            for entry in entries:
                ts = entry.get("ts") or ""
                ticket = entry.get("ticket_id") or "unknown"
                user = entry.get("user") or "unknown"
                note = entry.get("note") or ""
                lines.append(f"- {ts} [{ticket}] {user}: {note}")
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{week}.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
