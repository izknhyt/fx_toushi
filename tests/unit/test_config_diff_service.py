from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config.diff import ConfigDiffService


def _write_yaml(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for child_key, child_val in value.items():
                lines.append(f"  {child_key}: {child_val}")
        else:
            lines.append(f"{key}: {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_config_diff_risk_levels(tmp_path: Path) -> None:
    base = tmp_path / "base.yaml"
    target = tmp_path / "target.yaml"
    _write_yaml(base, {"risk": {"max_r": 0.5}, "execution": {"spread_guard": 2}})
    _write_yaml(target, {"risk": {"max_r": 0.7}, "execution": {"spread_guard": 3}})
    risk_cfg = tmp_path / "risk.yaml"
    risk_cfg.write_text(
        "\n".join(
            [
                "critical_paths:",
                "  - risk.max_r",
                "risk_paths:",
                "  - execution.*",
            ]
        ),
        encoding="utf-8",
    )
    service = ConfigDiffService(
        risk_config_path=risk_cfg,
        schema_path=tmp_path / "missing_schema.json",
        audit_log=tmp_path / "audit.jsonl",
    )
    diff_entries = service.diff(base, target)
    risk_levels = {entry.path: entry.risk_level for entry in diff_entries}
    assert risk_levels["risk.max_r"] == "critical"
    assert risk_levels["execution.spread_guard"] == "risk"


def test_config_diff_signature(tmp_path: Path) -> None:
    crypto = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    serialization = pytest.importorskip("cryptography.hazmat.primitives.serialization")
    key = crypto.Ed25519PrivateKey.generate()
    private_key_path = tmp_path / "sign.key"
    private_key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    base = tmp_path / "base.yaml"
    target = tmp_path / "target.yaml"
    _write_yaml(base, {"risk": {"max_r": 0.5}})
    _write_yaml(target, {"risk": {"max_r": 0.7}})
    service = ConfigDiffService(
        risk_config_path=tmp_path / "risk.yaml",
        schema_path=tmp_path / "missing_schema.json",
        audit_log=tmp_path / "audit.jsonl",
    )
    diff_entries = service.diff(base, target)
    signed = service.prepare_signature(
        diff_entries,
        profile_from="base",
        profile_to="target",
        private_key_path=private_key_path,
        signer="tester",
        signature_dir=tmp_path / "signatures",
    )
    assert signed.signature
    assert signed.signature_path.exists()
