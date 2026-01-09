"""Config registry stub."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


class ConfigRegistry:
    def __init__(self, path: str | Path = "config/app.yaml") -> None:
        self._path = Path(path)

    def load(self) -> Mapping[str, Any]:
        if not self._path.exists():
            return {}
        return yaml.safe_load(self._path.read_text(encoding="utf-8"))


__all__ = ["ConfigRegistry"]
