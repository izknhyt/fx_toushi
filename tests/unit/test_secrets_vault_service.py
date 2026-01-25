from __future__ import annotations

import base64
from pathlib import Path

import pytest

from src.infra.secrets import SecretDecryptionError, SecretsVaultService


def _set_key(monkeypatch: pytest.MonkeyPatch, key_bytes: bytes) -> None:
    monkeypatch.setenv("TRADECTL_SECRET_VAULT_KEY", base64.b64encode(key_bytes).decode("utf-8"))


def test_store_and_load_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_key(monkeypatch, b"A" * 32)
    secrets_dir = tmp_path / "secret"
    metadata_path = secrets_dir / "metadata.json"
    audit_path = tmp_path / "audit.jsonl"
    service = SecretsVaultService(
        secrets_dir=secrets_dir,
        metadata_path=metadata_path,
        audit_path=audit_path,
    )
    payload = {"token": "abc123", "owner": "ops"}
    secret_path = service.store("broker/demo", payload, rotation_at="2026-02-01T00:00:00Z")
    loaded = service.load("broker/demo")

    assert loaded == payload
    assert secret_path.exists()
    assert metadata_path.exists()
    assert (secret_path.stat().st_mode & 0o777) == 0o600
    assert (metadata_path.stat().st_mode & 0o777) == 0o600


def test_invalid_key_length_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_key(monkeypatch, b"B" * 16)
    service = SecretsVaultService(secrets_dir=tmp_path / "secret")
    with pytest.raises(SecretDecryptionError):
        service.store("broker/demo", {"token": "oops"})
