from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data.manifest_signer import DataManifestSigner


def test_manifest_signer_roundtrip(tmp_path: Path) -> None:
    crypto = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    serialization = pytest.importorskip("cryptography.hazmat.primitives.serialization")
    private_key = crypto.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_key_path = tmp_path / "private.pem"
    public_key_path = tmp_path / "public.pem"
    private_key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_key_path.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"schema_version": "data.manifest.v1", "generated_at": "2026-01-01T00:00:00Z", "entries": []}),
        encoding="utf-8",
    )

    signer = DataManifestSigner(signature_dir=tmp_path / "signatures")
    signed = signer.sign(manifest_path, private_key_path=private_key_path, signer="tester")
    assert signed.signature_path.exists()

    result = signer.verify(
        manifest_path,
        signature_path=signed.signature_path,
        public_key_path=public_key_path,
    )
    assert result["status"] == "ok"
