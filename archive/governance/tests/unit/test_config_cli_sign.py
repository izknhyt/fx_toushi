from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.interfaces.cli.config import sign as config_sign


def test_config_sign_accepts_diff_payload(tmp_path: Path) -> None:
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

    diff_path = tmp_path / "diff.json"
    diff_payload = {
        "status": "ok",
        "diff": [
            {
                "path": "risk.max_r",
                "from": 0.5,
                "to": 0.7,
                "change_type": "changed",
                "risk_level": "critical",
            }
        ],
    }
    diff_path.write_text(json.dumps(diff_payload), encoding="utf-8")

    payload = config_sign(
        diff_path=diff_path,
        profile_from="paper",
        profile_to="live",
        private_key_path=private_key_path,
        signer="tester",
    )
    assert payload["status"] == "ok"
    signed = payload["signed"]
    assert isinstance(signed, dict)
    assert Path(signed["signature_path"]).exists()
