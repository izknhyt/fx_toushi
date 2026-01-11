"""Data manifest service for tracking dataset provenance."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(slots=True)
class ManifestEntry:
    id: str
    kind: str
    path: str
    hash_sha256: str
    rows: int | None = None
    timespan: str | None = None
    source: str | None = None
    owner: str | None = None
    reviewer: str | None = None
    validation_playbook_id: str | None = None
    status: str = "provisional"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "path": self.path,
            "hash_sha256": self.hash_sha256,
            "rows": self.rows,
            "timespan": self.timespan,
            "source": self.source,
            "owner": self.owner,
            "reviewer": self.reviewer,
            "validation_playbook_id": self.validation_playbook_id,
            "status": self.status,
            "tags": list(self.tags),
        }


@dataclass(slots=True)
class DatasetManifest:
    schema_version: str
    generated_at: str
    entries: list[ManifestEntry]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "entries": [entry.to_dict() for entry in self.entries],
        }


class DataManifestService:
    def __init__(self, *, path: Path = Path("reports/data_manifest.json")) -> None:
        self._path = path
        self._manifest = self._load()

    def _load(self) -> DatasetManifest:
        if not self._path.exists():
            return DatasetManifest(schema_version="data.manifest.v1", generated_at=_utcnow_iso(), entries=[])
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        entries = []
        for raw in payload.get("entries", []):
            entries.append(
                ManifestEntry(
                    id=str(raw.get("id") or ""),
                    kind=str(raw.get("kind") or "unknown"),
                    path=str(raw.get("path") or ""),
                    hash_sha256=str(raw.get("hash_sha256") or ""),
                    rows=raw.get("rows"),
                    timespan=raw.get("timespan"),
                    source=raw.get("source"),
                    owner=raw.get("owner"),
                    reviewer=raw.get("reviewer"),
                    validation_playbook_id=raw.get("validation_playbook_id"),
                    status=str(raw.get("status") or "provisional"),
                    tags=list(raw.get("tags") or []),
                )
            )
        return DatasetManifest(
            schema_version=str(payload.get("schema_version") or "data.manifest.v1"),
            generated_at=str(payload.get("generated_at") or _utcnow_iso()),
            entries=entries,
        )

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._manifest.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @property
    def entries(self) -> list[ManifestEntry]:
        return list(self._manifest.entries)

    def record(
        self,
        *,
        path: Path,
        kind: str,
        owner: str | None = None,
        playbook_id: str | None = None,
        tags: list[str] | None = None,
        force: bool = False,
    ) -> ManifestEntry:
        if not path.exists():
            raise FileNotFoundError(str(path))
        entry_id = str(uuid.uuid4())
        file_hash = _hash_file(path)
        entry = ManifestEntry(
            id=entry_id,
            kind=kind,
            path=str(path),
            hash_sha256=file_hash,
            rows=None,
            timespan=None,
            source=None,
            owner=owner,
            reviewer=None,
            validation_playbook_id=playbook_id,
            status="provisional",
            tags=list(tags or []),
        )
        if not force and any(existing.id == entry_id for existing in self._manifest.entries):
            raise ValueError(f"manifest entry already exists: {entry_id}")
        self._manifest.entries.append(entry)
        self._manifest.generated_at = _utcnow_iso()
        self.save()
        return entry

    def verify(self, *, path: Path | None = None, entry_id: str | None = None) -> dict[str, object]:
        if path is None and entry_id is None:
            raise ValueError("path or entry_id required")
        entry = None
        if entry_id:
            for existing in self._manifest.entries:
                if existing.id == entry_id:
                    entry = existing
                    break
            if entry is None:
                raise ValueError(f"manifest entry not found: {entry_id}")
            target_path = Path(entry.path)
        else:
            target_path = path or Path("")
            for existing in self._manifest.entries:
                if existing.path == str(target_path):
                    entry = existing
                    break
        if not target_path.exists():
            raise FileNotFoundError(str(target_path))
        current_hash = _hash_file(target_path)
        expected_hash = entry.hash_sha256 if entry else None
        status = "ok" if expected_hash == current_hash else "mismatch"
        return {
            "status": status,
            "path": str(target_path),
            "entry_id": entry.id if entry else None,
            "expected_hash": expected_hash,
            "current_hash": current_hash,
        }

    def diff(self, *, base: Path, target: Path) -> dict[str, object]:
        base_manifest = DataManifestService(path=base)._manifest
        target_manifest = DataManifestService(path=target)._manifest
        base_index = {entry.id: entry for entry in base_manifest.entries}
        target_index = {entry.id: entry for entry in target_manifest.entries}
        added = [entry.to_dict() for entry_id, entry in target_index.items() if entry_id not in base_index]
        removed = [entry.to_dict() for entry_id, entry in base_index.items() if entry_id not in target_index]
        changed = []
        for entry_id, entry in target_index.items():
            if entry_id in base_index and entry.hash_sha256 != base_index[entry_id].hash_sha256:
                changed.append(entry.to_dict())
        return {
            "added": added,
            "removed": removed,
            "changed": changed,
        }


__all__ = ["DataManifestService", "DatasetManifest", "ManifestEntry"]
