"""Shared hashing helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path

__all__ = ["sha256_path"]


def sha256_path(path: Path) -> str:
    """Return sha256 digest for a file path with the standard prefix."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
