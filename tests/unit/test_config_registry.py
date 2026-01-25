from __future__ import annotations

from pathlib import Path

import pytest

from src.infra.config import ConfigChangeDenied, ConfigRegistry


def test_config_registry_apply_patch_requires_approval(tmp_path: Path) -> None:
    config_path = tmp_path / "app.yaml"
    config_path.write_text("risk:\n  limit: 1\n", encoding="utf-8")
    pending_dir = tmp_path / "pending"
    registry = ConfigRegistry(
        path=config_path,
        dangerous_keys=("risk.limit",),
        pending_dir=pending_dir,
    )
    with pytest.raises(ConfigChangeDenied):
        registry.apply_patch({"risk": {"limit": 2}}, actor="ops")

    result = registry.apply_patch({"risk": {"limit": 2}}, actor="ops", approved=True)
    assert result.status == "pending"
    assert result.pending_path is not None
    assert config_path.read_text(encoding="utf-8").strip() == "risk:\n  limit: 1"


def test_config_registry_snapshot_hash(tmp_path: Path) -> None:
    config_path = tmp_path / "app.yaml"
    config_path.write_text("risk:\n  limit: 1\n", encoding="utf-8")
    registry = ConfigRegistry(path=config_path)
    snapshot = registry.snapshot()
    assert snapshot.cfg_hash
