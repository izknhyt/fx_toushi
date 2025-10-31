from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.config import ConfigLoaderStub, ConfigNotFoundError


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

    loader = ConfigLoaderStub()

    def _loader(relative_path: str | Path) -> Any:
        path = project_root / Path(relative_path)
        try:
            return loader(path)
        except ConfigNotFoundError as exc:
            raise FileNotFoundError(str(exc)) from exc

    return _loader
