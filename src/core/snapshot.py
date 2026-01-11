"""Snapshot manager scaffolding for Codex implementation (detailed design §2.4)."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from src.persistence.events import EventWriter
from src.utils.hashing import sha256_path

DEFAULT_DATA_MISMATCH_LOG = Path("logs/events/snapshot.data_mismatch.jsonl")


class SnapshotError(Enum):
    """High level error signalling used by SnapshotManager placeholders."""

    SNAPSHOT_PERSIST_ERROR = "snapshot.persist_error"
    SNAPSHOT_HASH_ERROR = "snapshot.hash_error"
    SNAPSHOT_NOT_FOUND_ERROR = "snapshot.not_found"
    SNAPSHOT_CORRUPTED_ERROR = "snapshot.corrupted"
    DATA_MISMATCH_DETECTED = "snapshot.data_mismatch"
    HASH_COMPUTATION_ERROR = "snapshot.hash_computation_error"


@dataclass(frozen=True)
class SnapshotMetadata:
    """Metadata persisted alongside snapshot payloads."""

    cfg_hash: str
    data_hash: str
    actor: str | None
    created_at: datetime


@dataclass(frozen=True)
class SnapshotPersistResult:
    """Return value for successful persist operations."""

    path: Path
    checksum: str


@dataclass(frozen=True)
class SnapshotRestoreResult:
    """Container for restored snapshot state and warnings."""

    state: Any
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HashComparisonReport:
    """Result of comparing expected versus actual data hashes."""

    expected_hash: str
    actual_hash: str
    matches: bool


class SnapshotManager:
    """Filesystem oriented snapshot persistence skeleton."""

    def __init__(self, base_path: Path = Path("snapshots")) -> None:
        self.base_path = base_path
        self._logger = logging.getLogger(__name__)

    def persist(
        self,
        snapshot: Any,
        *,
        cfg_hash: str,
        data_hash: str,
        actor: str | None = None,
    ) -> SnapshotPersistResult:
        """Atomically write the provided snapshot to disk."""

        if not cfg_hash or not data_hash:
            raise RuntimeError(SnapshotError.SNAPSHOT_HASH_ERROR.value)
        metadata = SnapshotMetadata(
            cfg_hash=cfg_hash,
            data_hash=data_hash,
            actor=actor,
            created_at=datetime.utcnow(),
        )
        self._logger.debug("Preparing snapshot persist: base=%s", self.base_path)
        target_dir = Path(self.base_path)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "latest.json"
        tmp_path = target.with_suffix(".tmp")
        payload = {
            "metadata": {
                "cfg_hash": metadata.cfg_hash,
                "data_hash": metadata.data_hash,
                "actor": metadata.actor,
                "created_at": metadata.created_at.isoformat().replace("+00:00", "Z"),
            },
            "state": snapshot,
        }
        try:
            with tmp_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            tmp_path.replace(target)
            checksum = sha256_path(target)
        except OSError as exc:
            self._logger.error("snapshot.persist_failed", extra={"error": str(exc)})
            raise RuntimeError(SnapshotError.SNAPSHOT_PERSIST_ERROR.value) from exc
        return SnapshotPersistResult(path=target, checksum=checksum)

    def restore(self, path: Path | None = None) -> SnapshotRestoreResult:
        """Restore the most recent snapshot from disk."""

        target = path or self.base_path / "latest.json"
        self._logger.debug("Restoring snapshot: path=%s", target)
        if not target.exists():
            raise FileNotFoundError(target)
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(SnapshotError.SNAPSHOT_CORRUPTED_ERROR.value) from exc
        metadata = data.get("metadata") or {}
        cfg_hash = metadata.get("cfg_hash")
        data_hash = metadata.get("data_hash")
        if not cfg_hash or not data_hash:
            raise RuntimeError(SnapshotError.SNAPSHOT_HASH_ERROR.value)
        state = data.get("state")
        return SnapshotRestoreResult(state=state, warnings=())

    def compare_hash(self, data_hash: str, expected_hash: str) -> HashComparisonReport:
        """Compare the current data hash with the stored expectation."""

        if not data_hash or not expected_hash:
            raise RuntimeError(SnapshotError.HASH_COMPUTATION_ERROR.value)
        matches = data_hash == expected_hash
        if not matches:
            self._emit_data_mismatch(data_hash=data_hash, expected_hash=expected_hash)
        return HashComparisonReport(
            expected_hash=expected_hash, actual_hash=data_hash, matches=matches
        )

    def _emit_data_mismatch(self, *, data_hash: str, expected_hash: str) -> None:
        """Placeholder hook for raising the DataMismatch event."""

        payload = {
            "event": "snapshot.data_mismatch",
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
                "+00:00", "Z"
            ),
            "source": "snapshot",
            "expected_hash": expected_hash,
            "actual_hash": data_hash,
        }
        try:
            EventWriter(DEFAULT_DATA_MISMATCH_LOG).append(payload)
        except Exception as exc:  # pragma: no cover - best effort event logging
            self._logger.error(
                "snapshot.data_mismatch_event_failed", extra={"error": str(exc)}
            )
        self._logger.error(
            "Data mismatch detected: expected=%s actual=%s", expected_hash, data_hash
        )
        raise RuntimeError(SnapshotError.DATA_MISMATCH_DETECTED.value)

