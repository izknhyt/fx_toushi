"""Validation playbook CLI helpers."""

from __future__ import annotations

from pathlib import Path

from src.validation import sync_playbook


def playbook_sync(*, manifest_path: Path, output_dir: Path) -> dict[str, object]:
    return sync_playbook(manifest_path=manifest_path, output_dir=output_dir)


__all__ = ["playbook_sync"]
