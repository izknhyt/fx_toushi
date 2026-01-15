"""Device binding registry for risk consent enforcement."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:  # optional dependency for encryption at rest
    from cryptography.fernet import Fernet, InvalidToken
except Exception:  # pragma: no cover - optional dependency
    Fernet = None
    InvalidToken = Exception


class DeviceBindingError(Exception):
    """Base exception for device binding operations."""


class DeviceBindingExistsError(DeviceBindingError):
    """Raised when attempting to register a duplicate device binding."""


@dataclass(slots=True)
class DeviceBinding:
    device_id: str
    user: str
    fingerprint: str
    status: str
    registered_at: datetime
    revoked_at: datetime | None = None


class DeviceBindingService:
    """Persist and validate device bindings."""

    def __init__(
        self,
        *,
        registry_path: Path = Path("data/compliance/device_bindings.json"),
        audit_path: Path = Path("logs/audit/device_bindings.jsonl"),
        encryption_key: str | None = None,
        allow_plaintext: bool = False,
    ) -> None:
        self._registry_path = registry_path
        self._audit_path = audit_path
        self._encryption_key = encryption_key or os.getenv("DEVICE_BINDING_KEY")
        self._allow_plaintext = allow_plaintext
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)

    def register_device(
        self,
        *,
        user: str,
        fingerprint: str,
        force: bool = False,
    ) -> DeviceBinding:
        bindings = self._load_bindings()
        for binding in bindings:
            if binding.fingerprint == fingerprint and binding.status != "revoked":
                if not force:
                    raise DeviceBindingExistsError(fingerprint)
        device_id = _generate_device_id(bindings)
        record = DeviceBinding(
            device_id=device_id,
            user=user,
            fingerprint=fingerprint,
            status="active",
            registered_at=datetime.now(timezone.utc),
        )
        bindings.append(record)
        self._save_bindings(bindings)
        self._append_audit("audit.device_registered", record)
        return record

    def revoke_device(self, *, device_id: str, reason: str) -> DeviceBinding:
        bindings = self._load_bindings()
        for binding in bindings:
            if binding.device_id == device_id:
                binding.status = "revoked"
                binding.revoked_at = datetime.now(timezone.utc)
                self._save_bindings(bindings)
                self._append_audit("audit.device_revoked", binding, reason=reason)
                return binding
        raise DeviceBindingError(device_id)

    def list_devices(self, *, show_revoked: bool = False) -> list[DeviceBinding]:
        bindings = self._load_bindings()
        if show_revoked:
            return bindings
        return [binding for binding in bindings if binding.status != "revoked"]

    def validate_device(self, *, user: str, fingerprint: str) -> bool:
        for binding in self._load_bindings():
            if binding.user == user and binding.fingerprint == fingerprint:
                return binding.status == "active"
        return False

    def _load_bindings(self) -> list[DeviceBinding]:
        if not self._registry_path.exists():
            return []
        payload = json.loads(self._registry_path.read_text(encoding="utf-8"))
        if payload.get("encrypted"):
            decrypted = self._decrypt_payload(payload.get("payload"))
            payload = json.loads(decrypted)
        bindings = []
        for item in payload.get("devices", []):
            bindings.append(_binding_from_dict(item))
        return bindings

    def _save_bindings(self, bindings: list[DeviceBinding]) -> None:
        payload = {"devices": [_binding_to_dict(binding) for binding in bindings]}
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        if self._encryption_key:
            encrypted = self._encrypt_payload(serialized)
            wrapper = {"encrypted": True, "payload": encrypted}
            self._registry_path.write_text(
                json.dumps(wrapper, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        elif self._allow_plaintext:
            wrapper = {"encrypted": False, **payload}
            self._registry_path.write_text(
                json.dumps(wrapper, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        else:
            raise DeviceBindingError("DEVICE_BINDING_KEY is required for encrypted registry")
        os.chmod(self._registry_path, 0o600)

    def _append_audit(self, event: str, binding: DeviceBinding, reason: str | None = None) -> None:
        payload = {
            "event": event,
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "device_id": binding.device_id,
            "user": binding.user,
            "reason": reason,
        }
        with self._audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _encrypt_payload(self, payload: str) -> str:
        cipher = _build_cipher(self._encryption_key)
        token = cipher.encrypt(payload.encode("utf-8"))
        return token.decode("utf-8")

    def _decrypt_payload(self, token: str | None) -> str:
        if not token:
            raise DeviceBindingError("encrypted registry payload missing")
        cipher = _build_cipher(self._encryption_key)
        try:
            return cipher.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:  # pragma: no cover - defensive
            raise DeviceBindingError("invalid device binding encryption key") from exc


def _binding_from_dict(payload: dict[str, object]) -> DeviceBinding:
    registered_at = datetime.fromisoformat(str(payload.get("registered_at")).replace("Z", "+00:00"))
    revoked_at_raw = payload.get("revoked_at")
    revoked_at = (
        datetime.fromisoformat(str(revoked_at_raw).replace("Z", "+00:00"))
        if revoked_at_raw
        else None
    )
    return DeviceBinding(
        device_id=str(payload.get("device_id", "")),
        user=str(payload.get("user", "")),
        fingerprint=str(payload.get("fingerprint", "")),
        status=str(payload.get("status", "active")),
        registered_at=registered_at,
        revoked_at=revoked_at,
    )


def _binding_to_dict(binding: DeviceBinding) -> dict[str, object]:
    return {
        "device_id": binding.device_id,
        "user": binding.user,
        "fingerprint": binding.fingerprint,
        "status": binding.status,
        "registered_at": binding.registered_at.isoformat().replace("+00:00", "Z"),
        "revoked_at": binding.revoked_at.isoformat().replace("+00:00", "Z")
        if binding.revoked_at
        else None,
    }


def _generate_device_id(bindings: list[DeviceBinding]) -> str:
    date_stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    sequence = len(bindings) + 1
    return f"DEV-{date_stamp}-{sequence:02d}"


def _build_cipher(key: str | None):
    if Fernet is None:
        raise DeviceBindingError("cryptography is required for device binding encryption")
    if not key:
        raise DeviceBindingError("DEVICE_BINDING_KEY is required for encrypted registry")
    return Fernet(key.encode("utf-8"))


__all__ = [
    "DeviceBinding",
    "DeviceBindingError",
    "DeviceBindingExistsError",
    "DeviceBindingService",
]
