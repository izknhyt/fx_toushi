"""Minimal secret store integration used by broker adapters.

This is a lightweight placeholder for the design in §38.1; it stores JSON
payloads in the repo to support adapter wiring and tests until encrypted
storage is implemented.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


class SecretNotFoundError(RuntimeError):
    """Raised when a requested secret is missing."""


class SecretsVaultService:
    """Store/load secrets from JSON files with minimal metadata tracking."""

    def __init__(
        self,
        *,
        secrets_dir: Path = Path("config") / "secret",
        metadata_path: Path = Path("config") / "secret" / "metadata.json",
        audit_path: Path = Path("logs") / "audit" / "secrets.jsonl",
    ) -> None:
        self._secrets_dir = secrets_dir
        self._metadata_path = metadata_path
        self._audit_path = audit_path

    def load(self, secret_id: str, *, purpose: str | None = None) -> dict[str, Any]:
        path = self._secret_path(secret_id)
        if not path.exists():
            raise SecretNotFoundError(secret_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        self._update_metadata(secret_id, payload, action="load")
        self._append_audit(secret_id, action="load", purpose=purpose)
        return payload if isinstance(payload, dict) else {"value": payload}

    def store(
        self,
        secret_id: str,
        payload: Mapping[str, Any],
        *,
        rotation_at: str | None = None,
        purpose: str | None = None,
    ) -> Path:
        path = self._secret_path(secret_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._update_metadata(secret_id, payload, action="store", rotation_at=rotation_at)
        self._append_audit(secret_id, action="store", purpose=purpose)
        return path

    def rotation_due(self, *, within_days: int = 30) -> list[str]:
        metadata = self._load_metadata()
        if not metadata:
            return []
        cutoff = datetime.now(timezone.utc) + timedelta(days=within_days)
        due: list[str] = []
        for secret_id, entry in metadata.items():
            rotation_at = entry.get("rotation_at")
            if not rotation_at:
                continue
            try:
                when = datetime.fromisoformat(rotation_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            if when <= cutoff:
                due.append(secret_id)
        return sorted(set(due))

    def _secret_path(self, secret_id: str) -> Path:
        safe_id = secret_id.replace("/", "_")
        return self._secrets_dir / f"{safe_id}.json"

    def _load_metadata(self) -> dict[str, dict[str, Any]]:
        if not self._metadata_path.exists():
            return {}
        try:
            payload = json.loads(self._metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _update_metadata(
        self,
        secret_id: str,
        payload: Mapping[str, Any],
        *,
        action: str,
        rotation_at: str | None = None,
    ) -> None:
        metadata = self._load_metadata()
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        metadata[secret_id] = {
            "checksum": digest,
            "last_used_at": _utcnow_iso(),
            "rotation_at": rotation_at or metadata.get(secret_id, {}).get("rotation_at"),
            "action": action,
        }
        self._metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self._metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _append_audit(self, secret_id: str, *, action: str, purpose: str | None) -> None:
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "event": "audit.secrets",
            "ts": _utcnow_iso(),
            "action": action,
            "secret_id": secret_id,
            "purpose": purpose,
        }
        with self._audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["SecretsVaultService", "SecretNotFoundError"]
