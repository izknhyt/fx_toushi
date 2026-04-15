from __future__ import annotations

from pathlib import Path

import pytest

from src.compliance.device_binding import DeviceBindingExistsError, DeviceBindingService


def test_device_binding_register_and_list(tmp_path: Path) -> None:
    service = DeviceBindingService(
        registry_path=tmp_path / "device_bindings.json",
        audit_path=tmp_path / "device_bindings_audit.jsonl",
        allow_plaintext=True,
    )
    binding = service.register_device(user="ops", fingerprint="fp-1")
    assert binding.device_id
    devices = service.list_devices()
    assert len(devices) == 1
    assert devices[0].fingerprint == "fp-1"


def test_device_binding_duplicate(tmp_path: Path) -> None:
    service = DeviceBindingService(
        registry_path=tmp_path / "device_bindings.json",
        audit_path=tmp_path / "device_bindings_audit.jsonl",
        allow_plaintext=True,
    )
    service.register_device(user="ops", fingerprint="fp-1")
    with pytest.raises(DeviceBindingExistsError):
        service.register_device(user="ops", fingerprint="fp-1")


def test_device_binding_revoke(tmp_path: Path) -> None:
    service = DeviceBindingService(
        registry_path=tmp_path / "device_bindings.json",
        audit_path=tmp_path / "device_bindings_audit.jsonl",
        allow_plaintext=True,
    )
    binding = service.register_device(user="ops", fingerprint="fp-1")
    revoked = service.revoke_device(device_id=binding.device_id, reason="lost")
    assert revoked.status == "revoked"
    assert service.list_devices() == []
