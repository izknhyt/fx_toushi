"""Access review CLI helpers (M2 governance)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["start_review", "AccessReviewError"]

DEFAULT_OUTPUT_DIR = Path("reports/governance")
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")


class AccessReviewError(RuntimeError):
    """Raised when access review evidence cannot be produced."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def start_review(
    *,
    scope: str,
    due_at: str | None = None,
    note: str | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    ops_worklog_path: Path = DEFAULT_OPS_WORKLOG,
) -> dict[str, object]:
    """Start an access review and persist evidence."""

    timestamp = _utcnow()
    review_id = f"access-review-{datetime.now(timezone.utc):%Y%m%d}"
    payload: dict[str, object] = {
        "review_id": review_id,
        "scope": scope,
        "started_at": timestamp,
        "due_at": due_at,
        "note": note,
        "status": "queued",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"access_review_{datetime.now(timezone.utc):%Y%m%d}.json"
    try:
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise AccessReviewError(f"Failed to write access review: {output_path}") from exc

    worklog = {
        "timestamp": timestamp,
        "task": "access_review_start",
        "scope": scope,
        "due_at": due_at,
        "note": note,
        "review_id": review_id,
        "evidence": str(output_path),
    }
    _append_jsonl(ops_worklog_path, worklog)

    logger.info("access.review.started", extra={"review_id": review_id, "scope": scope})
    payload["output_path"] = str(output_path)
    return payload
