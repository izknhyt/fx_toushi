"""Config loading helpers used by test fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore[assignment]

__all__ = [
    "ConfigLoaderStub",
    "ConfigError",
    "ConfigNotFoundError",
    "ConfigFormatNotSupportedError",
]


class ConfigError(RuntimeError):
    """Base error for config fixture helpers."""


class ConfigNotFoundError(ConfigError, FileNotFoundError):
    """Raised when a config file is missing from the repository tree."""


class ConfigFormatNotSupportedError(ConfigError):
    """Raised when the config fixture cannot parse the requested format."""


class ConfigLoaderStub:
    """Load JSON or YAML configuration files for tests.

    The helper centralises error handling so that tests can reference consistent
    exception types (e.g. :class:`ConfigNotFoundError`).
    """

    def __call__(self, path: Path) -> Any:
        if not path.exists():
            raise ConfigNotFoundError(f"Config fixture could not locate file: {path}")

        suffix = path.suffix.lower()
        if suffix == ".json":
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)

        if suffix in {".yaml", ".yml"}:
            if yaml is None:
                raise ConfigFormatNotSupportedError("PyYAML is required to load YAML config files")
            with path.open("r", encoding="utf-8") as handle:
                return yaml.safe_load(handle.read())

        return path.read_text(encoding="utf-8")
