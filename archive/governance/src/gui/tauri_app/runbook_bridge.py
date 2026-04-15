"""Runbook bridge to fetch and acknowledge GUI runbooks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RunbookPayload:
    runbook_id: str
    content: str
    source_path: str
    updated_at: str
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "runbook_id": self.runbook_id,
            "content": self.content,
            "source_path": self.source_path,
            "updated_at": self.updated_at,
            "content_hash": self.content_hash,
        }


class RunbookBridge:
    def __init__(
        self,
        *,
        runbook_dir: Path = Path("docs/runbooks"),
        ack_log_path: Path = Path("reports/gui/runbook_ack.jsonl"),
    ) -> None:
        self._runbook_dir = runbook_dir
        self._ack_log_path = ack_log_path

    def fetch(self, runbook_id: str) -> RunbookPayload:
        path = self._resolve_path(runbook_id)
        content = path.read_text(encoding="utf-8")
        content_hash = _hash_content(content)
        payload = RunbookPayload(
            runbook_id=runbook_id,
            content=content,
            source_path=str(path),
            updated_at=_mtime_iso(path),
            content_hash=content_hash,
        )
        return payload

    def acknowledge(self, *, runbook_id: str, user: str | None = None) -> dict[str, Any]:
        payload = self.fetch(runbook_id)
        entry = {
            "ts": _utcnow_iso(),
            "runbook_id": runbook_id,
            "user": user or "unknown",
            "status": "acknowledged",
            "updated_at": payload.updated_at,
            "content_hash": payload.content_hash,
        }
        self._ack_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._ack_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")
        return entry

    def _resolve_path(self, runbook_id: str) -> Path:
        if runbook_id.endswith(".md"):
            candidate = Path(runbook_id)
            if candidate.exists():
                return candidate
            return self._runbook_dir / runbook_id
        candidate = self._runbook_dir / f"{runbook_id}.md"
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"runbook not found: {runbook_id}")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _mtime_iso(path: Path) -> str:
    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash_content(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


__all__ = ["RunbookPayload", "RunbookBridge"]
