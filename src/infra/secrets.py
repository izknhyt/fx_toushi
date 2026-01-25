"""Secrets vault integration used by broker adapters (design §38.1)."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

DEFAULT_KEYCHAIN_SERVICE = "TRADECTL_SECRET_VAULT"
DEFAULT_KEY_ENV = "TRADECTL_SECRET_VAULT_KEY"
_KEY_BYTES = 32
_FILE_MODE = 0o600

class SecretNotFoundError(RuntimeError):
    """Raised when a requested secret is missing."""


class SecretDecryptionError(RuntimeError):
    """Raised when decryption fails."""


class SecretMetadataMissing(RuntimeError):
    """Raised when secret metadata is missing."""


class SecretsVaultService:
    """Store/load secrets from JSON files with minimal metadata tracking."""

    def __init__(
        self,
        *,
        secrets_dir: Path = Path("config") / "secret",
        metadata_path: Path = Path("config") / "secret" / "metadata.json",
        audit_path: Path | None = None,
        key_env: str = DEFAULT_KEY_ENV,
        keychain_service: str = DEFAULT_KEYCHAIN_SERVICE,
    ) -> None:
        self._secrets_dir = secrets_dir
        self._metadata_path = metadata_path
        self._audit_path = audit_path
        self._key_env = key_env
        self._keychain_service = keychain_service

    def load(self, secret_id: str, *, purpose: str | None = None) -> dict[str, Any]:
        enc_path = self._secret_path(secret_id)
        legacy_path = self._legacy_secret_path(secret_id)
        if not enc_path.exists() and not legacy_path.exists():
            raise SecretNotFoundError(secret_id)
        payload: dict[str, Any]
        if enc_path.exists():
            payload = self._decrypt_payload(enc_path)
        else:
            logger.warning("secrets.legacy_plaintext", extra={"secret_id": secret_id})
            payload = json.loads(legacy_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            payload = {"value": payload}
        if not self._load_metadata().get(secret_id):
            logger.warning("secrets.metadata_missing", extra={"secret_id": secret_id})
        self._update_metadata(secret_id, payload, action="load")
        self._append_audit(
            secret_id,
            action="load",
            purpose=purpose,
            checksum=self._checksum(payload),
            rotation_at=self._load_metadata().get(secret_id, {}).get("rotation_at"),
        )
        return payload

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
        self._encrypt_payload(path, payload)
        self._update_metadata(
            secret_id,
            payload,
            action="store",
            rotation_at=rotation_at,
            algorithm="aes-256-gcm",
        )
        self._append_audit(
            secret_id,
            action="store",
            purpose=purpose,
            checksum=self._checksum(payload),
            rotation_at=rotation_at,
        )
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
        return self._secrets_dir / f"secret_{safe_id}.enc"

    def _legacy_secret_path(self, secret_id: str) -> Path:
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
        algorithm: str | None = None,
    ) -> None:
        metadata = self._load_metadata()
        digest = self._checksum(payload)
        metadata[secret_id] = {
            "checksum": digest,
            "last_used_at": _utcnow_iso(),
            "rotation_at": rotation_at or metadata.get(secret_id, {}).get("rotation_at"),
            "action": action,
            "algorithm": algorithm or metadata.get(secret_id, {}).get("algorithm", "aes-256-gcm"),
        }
        self._metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self._metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _set_private_permissions(self._metadata_path)

    def _append_audit(
        self,
        secret_id: str,
        *,
        action: str,
        purpose: str | None,
        checksum: str | None,
        rotation_at: str | None,
    ) -> None:
        audit_path = _resolve_audit_path(self._audit_path)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "event": "audit.secrets",
            "ts": _utcnow_iso(),
            "action": action,
            "secret_id": secret_id,
            "purpose": purpose,
            "checksum": checksum,
            "rotation_at": rotation_at,
        }
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _checksum(self, payload: Mapping[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def _encrypt_payload(self, path: Path, payload: Mapping[str, Any]) -> None:
        key = self._resolve_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        envelope = {
            "alg": "AES-256-GCM",
            "nonce": base64.b64encode(nonce).decode("utf-8"),
            "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
        }
        path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
        _set_private_permissions(path)

    def _decrypt_payload(self, path: Path) -> dict[str, Any]:
        key = self._resolve_key()
        envelope = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(envelope, dict):
            raise SecretDecryptionError("invalid envelope")
        if envelope.get("alg") != "AES-256-GCM":
            raise SecretDecryptionError("unsupported encryption algorithm")
        try:
            nonce = base64.b64decode(envelope["nonce"])
            ciphertext = base64.b64decode(envelope["ciphertext"])
        except Exception as exc:  # pragma: no cover - defensive
            raise SecretDecryptionError("invalid ciphertext") from exc
        if len(nonce) != 12:
            raise SecretDecryptionError("invalid nonce length")
        aesgcm = AESGCM(key)
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        except Exception as exc:  # pragma: no cover - defensive
            raise SecretDecryptionError("decryption failed") from exc
        payload = json.loads(plaintext.decode("utf-8"))
        return payload if isinstance(payload, dict) else {"value": payload}

    def _resolve_key(self) -> bytes:
        env_key = os.getenv(self._key_env)
        if env_key:
            return _decode_key(env_key)
        keychain_key = _load_keychain_secret(self._keychain_service)
        if keychain_key:
            return _decode_key(keychain_key)
        raise SecretDecryptionError(
            f"secret vault key missing; set {self._key_env} or store in keychain"
        )


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_audit_path(audit_path: Path | None) -> Path:
    if audit_path is not None:
        return audit_path
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Path("logs/audit") / f"secrets_{stamp}.jsonl"


def _decode_key(raw: str) -> bytes:
    raw = raw.strip()
    try:
        if len(raw) == 64:
            key = bytes.fromhex(raw)
        else:
            key = base64.b64decode(raw)
    except (ValueError, binascii.Error) as exc:
        raise SecretDecryptionError("invalid secret vault key encoding") from exc
    if len(key) != _KEY_BYTES:
        raise SecretDecryptionError(
            f"secret vault key must be {_KEY_BYTES} bytes, got {len(key)}"
        )
    return key


def _load_keychain_secret(service: str) -> str | None:
    if os.name != "posix":
        return None
    if os.getenv("TRADECTL_DISABLE_KEYCHAIN"):
        return None
    try:
        import subprocess

        result = subprocess.run(
            ["security", "find-generic-password", "-a", os.getenv("USER", ""), "-s", service, "-w"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except Exception:
        return None


def _set_private_permissions(path: Path) -> None:
    try:
        path.chmod(_FILE_MODE)
    except OSError:
        logger.debug("secrets.permission_set_failed", extra={"path": str(path)})


__all__ = [
    "SecretsVaultService",
    "SecretNotFoundError",
    "SecretDecryptionError",
    "SecretMetadataMissing",
]
