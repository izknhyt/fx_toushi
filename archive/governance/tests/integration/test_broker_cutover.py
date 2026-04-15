from __future__ import annotations

import pytest

from pathlib import Path

from src.interfaces.cli.release_cutover import (
    CutoverBlockedError,
    broker_cutover_generate,
    broker_cutover_verify,
)


def test_broker_cutover_generate_returns_payload(tmp_path: Path) -> None:
    payload = broker_cutover_generate(profile="paper", base_dir=tmp_path / "release")
    assert payload["status"] == "ok"
    assert payload["profile"] == "paper"


def test_broker_cutover_verify_blocks_by_default(tmp_path: Path) -> None:
    with pytest.raises(CutoverBlockedError):
        broker_cutover_verify(profile="paper", base_dir=tmp_path / "release")
