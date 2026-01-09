"""CLI helpers for ``tradectl funding`` subcommands."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["FundingSyncError", "funding_sync", "funding_status"]


class FundingSyncError(RuntimeError):
    """Raised when the funding CSV reconciliation fails."""


@dataclass(slots=True)
class FundingState:
    """Serialized representation of ``funding_state.json``."""

    schema_version: str
    last_synced_at: str
    csv_path: str
    shadow_path: str
    csv_sha256: str
    shadow_sha256: str
    prepared_by: str | None
    reviewed_by: str | None
    approved_by: str | None
    shadow_reconciliation: str
    pair_count: int


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FundingSyncError(f"CSV not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            normalised = {key.strip(): (value or "").strip() for key, value in row.items()}
            rows.append(normalised)
    if not rows:
        raise FundingSyncError(f"CSV empty: {path}")
    return rows


def _index(rows: Iterable[dict[str, str]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        pair = row.get("pair")
        if not pair:
            raise FundingSyncError("CSV row missing 'pair' column")
        result[pair] = row
    return result


def _compare(main_rows: list[dict[str, str]], shadow_rows: list[dict[str, str]]) -> None:
    main_index = _index(main_rows)
    shadow_index = _index(shadow_rows)
    missing = sorted(set(main_index) ^ set(shadow_index))
    if missing:
        raise FundingSyncError(f"Pair mismatch between CSVs: {missing}")
    mismatches: list[str] = []
    for pair, row in main_index.items():
        shadow_row = shadow_index[pair]
        if row != shadow_row:
            mismatches.append(pair)
    if mismatches:
        raise FundingSyncError(f"Detected {len(mismatches)} row mismatches: {mismatches[:3]}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def funding_sync(
    *,
    csv_path: Path,
    shadow_path: Path | None,
    state_path: Path,
    prepared_by: str | None,
    reviewed_by: str | None,
    approved_by: str | None,
    dry_run: bool,
) -> FundingState:
    """Validate funding CSVs and update ``funding_state.json``."""

    main_rows = _read_csv(csv_path)
    shadow_rows: list[dict[str, str]] = []
    if shadow_path:
        shadow_rows = _read_csv(shadow_path)
        _compare(main_rows, shadow_rows)
    else:
        shadow_path = csv_path
        shadow_rows = main_rows

    timestamp = _utcnow_iso()
    main_hash = _sha256(csv_path)
    shadow_hash = _sha256(shadow_path)

    state = FundingState(
        schema_version="funding_state.v1",
        last_synced_at=timestamp,
        csv_path=str(csv_path),
        shadow_path=str(shadow_path),
        csv_sha256=main_hash,
        shadow_sha256=shadow_hash,
        prepared_by=prepared_by,
        reviewed_by=reviewed_by,
        approved_by=approved_by,
        shadow_reconciliation="pass",
        pair_count=len(main_rows),
    )

    if not dry_run:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return state


def funding_status(*, state_path: Path) -> dict[str, Any]:
    """Return the last recorded funding state."""

    if not state_path.exists():
        return {
            "schema_version": "funding_state.v1",
            "status": "missing",
            "state_path": str(state_path),
        }
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload.setdefault("schema_version", "funding_state.v1")
    payload["status"] = "ok"
    payload["state_path"] = str(state_path)
    return payload
