"""Research artifact registry with DataManifest integration."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.data.manifest import DataManifestService

__all__ = ["ResearchArtifactRegistry", "ResearchArtifact"]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class ResearchArtifact:
    artifact_id: str
    name: str
    kind: str
    path: str
    owner: str | None
    idea_id: str | None
    created_at: str
    manifest_entry_id: str | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "name": self.name,
            "kind": self.kind,
            "path": self.path,
            "owner": self.owner,
            "idea_id": self.idea_id,
            "created_at": self.created_at,
            "manifest_entry_id": self.manifest_entry_id,
            "status": self.status,
        }


class ResearchArtifactRegistry:
    def __init__(
        self,
        *,
        registry_path: Path = Path("reports") / "research" / "artifacts.json",
        manifest_path: Path = Path("reports") / "data_manifest.json",
    ) -> None:
        self._registry_path = registry_path
        self._manifest_path = manifest_path
        self._records = self._load()

    def register(
        self,
        *,
        path: Path,
        kind: str,
        name: str | None = None,
        owner: str | None = None,
        idea_id: str | None = None,
        playbook_id: str | None = None,
    ) -> ResearchArtifact:
        if not path.exists():
            raise FileNotFoundError(str(path))
        manifest = DataManifestService(path=self._manifest_path)
        manifest_entry = manifest.record(
            path=path, kind=kind, owner=owner, playbook_id=playbook_id
        )
        artifact = ResearchArtifact(
            artifact_id=str(uuid.uuid4()),
            name=name or path.stem,
            kind=kind,
            path=str(path),
            owner=owner,
            idea_id=idea_id,
            created_at=_utcnow_iso(),
            manifest_entry_id=manifest_entry.id,
            status="registered",
        )
        self._records.append(artifact)
        self._save()
        return artifact

    def list(self) -> list[ResearchArtifact]:
        return list(self._records)

    def _load(self) -> list[ResearchArtifact]:
        if not self._registry_path.exists():
            return []
        payload = json.loads(self._registry_path.read_text(encoding="utf-8"))
        records = []
        for raw in payload.get("artifacts", []):
            records.append(
                ResearchArtifact(
                    artifact_id=str(raw.get("artifact_id") or ""),
                    name=str(raw.get("name") or ""),
                    kind=str(raw.get("kind") or ""),
                    path=str(raw.get("path") or ""),
                    owner=raw.get("owner"),
                    idea_id=raw.get("idea_id"),
                    created_at=str(raw.get("created_at") or _utcnow_iso()),
                    manifest_entry_id=raw.get("manifest_entry_id"),
                    status=str(raw.get("status") or "registered"),
                )
            )
        return records

    def _save(self) -> None:
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": "research.artifacts.v1", "artifacts": [r.to_dict() for r in self._records]}
        self._registry_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
