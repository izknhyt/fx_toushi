"""Manifest signing utilities for data/audit integrity."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

try:  # pragma: no cover - optional dependency
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
except ModuleNotFoundError:  # pragma: no cover
    Ed25519PrivateKey = None  # type: ignore[assignment]
    Ed25519PublicKey = None  # type: ignore[assignment]
    serialization = None  # type: ignore[assignment]


class ManifestSignatureError(RuntimeError):
    """Raised when manifest signing or verification fails."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _manifest_sha(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(slots=True)
class ManifestSignature:
    manifest_path: Path
    sha256: str
    signed_at: str
    signer: str
    signature: str
    signature_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_path": str(self.manifest_path),
            "sha256": self.sha256,
            "signed_at": self.signed_at,
            "signer": self.signer,
            "signature": self.signature,
            "signature_path": str(self.signature_path),
        }


class DataManifestSigner:
    def __init__(self, *, signature_dir: Path = Path("reports/data_manifest_signatures")) -> None:
        self._signature_dir = signature_dir

    def sign(
        self,
        manifest_path: Path,
        *,
        private_key_path: Path,
        signer: str = "local",
    ) -> ManifestSignature:
        if Ed25519PrivateKey is None or serialization is None:
            raise ManifestSignatureError("cryptography is required for signing")
        if not manifest_path.exists():
            raise FileNotFoundError(str(manifest_path))
        sha_value = _manifest_sha(manifest_path)
        signature = _sign_sha(sha_value, private_key_path)
        self._signature_dir.mkdir(parents=True, exist_ok=True)
        signature_path = self._signature_dir / f"{manifest_path.stem}.sig"
        payload = {
            "schema_version": "data.manifest.signature.v1",
            "manifest_path": str(manifest_path),
            "sha256": sha_value,
            "signed_at": _utcnow_iso(),
            "signer": signer,
            "signature": signature,
        }
        signature_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return ManifestSignature(
            manifest_path=manifest_path,
            sha256=sha_value,
            signed_at=payload["signed_at"],
            signer=signer,
            signature=signature,
            signature_path=signature_path,
        )

    def verify(
        self,
        manifest_path: Path,
        *,
        signature_path: Path,
        public_key_path: Path,
    ) -> dict[str, Any]:
        if Ed25519PublicKey is None or serialization is None:
            raise ManifestSignatureError("cryptography is required for verification")
        if not manifest_path.exists():
            raise FileNotFoundError(str(manifest_path))
        if not signature_path.exists():
            raise FileNotFoundError(str(signature_path))
        payload = json.loads(signature_path.read_text(encoding="utf-8"))
        sha_value = _manifest_sha(manifest_path)
        signature = payload.get("signature")
        if not isinstance(signature, str):
            raise ManifestSignatureError("signature missing in signature file")
        ok = _verify_signature(sha_value, signature, public_key_path)
        return {
            "status": "ok" if ok else "mismatch",
            "manifest_path": str(manifest_path),
            "signature_path": str(signature_path),
            "sha256": sha_value,
            "signature": signature,
            "signer": payload.get("signer"),
        }


def _sign_sha(sha_value: str, private_key_path: Path) -> str:
    if Ed25519PrivateKey is None or serialization is None:
        raise ManifestSignatureError("cryptography is required for signing")
    key_bytes = private_key_path.read_bytes()
    key = serialization.load_pem_private_key(key_bytes, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ManifestSignatureError("unsupported private key type")
    signature = key.sign(sha_value.encode("utf-8"))
    return signature.hex()


def _verify_signature(sha_value: str, signature_hex: str, public_key_path: Path) -> bool:
    if Ed25519PublicKey is None or serialization is None:
        raise ManifestSignatureError("cryptography is required for verification")
    key_bytes = public_key_path.read_bytes()
    key = serialization.load_pem_public_key(key_bytes)
    if not isinstance(key, Ed25519PublicKey):
        raise ManifestSignatureError("unsupported public key type")
    try:
        key.verify(bytes.fromhex(signature_hex), sha_value.encode("utf-8"))
    except Exception:
        return False
    return True


__all__ = ["DataManifestSigner", "ManifestSignature", "ManifestSignatureError"]
