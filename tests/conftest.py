from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - fallback for environments without PyYAML
    yaml = None  # type: ignore[assignment]


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the repository root path for test helpers."""

    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def load_json_schema(project_root: Path) -> Callable[[str | Path], dict[str, Any]]:
    """Load a JSON schema relative to the repository root."""

    def _loader(relative_path: str | Path) -> dict[str, Any]:
        path = project_root / Path(relative_path)
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    return _loader


@pytest.fixture(scope="session")
def load_config(project_root: Path) -> Callable[[str | Path], Any]:
    """Load a config file (JSON/YAML) relative to the repository root."""

    def _loader(relative_path: str | Path) -> Any:
        path = project_root / Path(relative_path)
        if not path.exists():
            msg = f"Config fixture could not locate file: {path}"
            raise FileNotFoundError(msg)

        suffix = path.suffix.lower()
        if suffix == ".json":
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)

        if suffix in {".yaml", ".yml"}:
            if yaml is None:  # pragma: no cover - optional dependency for YAML parsing
                msg = "PyYAML is required to load YAML config files"
                raise RuntimeError(msg)
            with path.open("r", encoding="utf-8") as handle:
                return yaml.safe_load(handle.read())

        return path.read_text(encoding="utf-8")

    return _loader
