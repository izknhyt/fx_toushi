from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.config import ConfigLoaderStub, ConfigNotFoundError


_ORIG_OPEN = Path.open
_ORIG_WRITE_TEXT = Path.write_text
_ORIG_WRITE_BYTES = Path.write_bytes
_ORIG_READ_TEXT = Path.read_text
_ORIG_READ_BYTES = Path.read_bytes
_ORIG_EXISTS = Path.exists
_ORIG_IS_FILE = Path.is_file
_ORIG_IS_DIR = Path.is_dir
_ORIG_MKDIR = Path.mkdir
_ORIG_TOUCH = Path.touch
_ORIG_UNLINK = Path.unlink


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


@pytest.fixture(autouse=True)
def isolate_runtime_outputs(tmp_path: Path, project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect mutable runtime outputs (metrics/reports/etc.) into tmp during tests.

    This keeps the git worktree clean even when full pytest or CLI flows run.
    """

    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)

    redirected: dict[str, Path] = {}
    mutable_prefixes = (
        "metrics",
        "reports",
        "snapshots",
        "logs",
        "jsonl",
        "orders",
        "evidence",
        "benchmark_runs",
        "data/queues",
        "data/manual_fallback/jobs",
        "config/signatures",
        "config/pending",
    )
    mutable_files = {
        "audit.jsonl",
        "ops_worklog.jsonl",
        "automation_effect.jsonl",
        "ignored.jsonl",
    }

    def _relative(path: Path) -> Path | None:
        if path.is_absolute():
            try:
                return path.relative_to(project_root)
            except ValueError:
                return None
        return path

    def _is_mutable(path: Path) -> bool:
        rel = _relative(path)
        if rel is None:
            return False
        rel_str = rel.as_posix()
        if rel_str in mutable_files:
            return True
        return any(rel_str == prefix or rel_str.startswith(f"{prefix}/") for prefix in mutable_prefixes)

    def _runtime_path(path: Path, *, for_write: bool) -> Path:
        rel = _relative(path)
        if rel is None:
            return path
        target = runtime_root / rel
        if for_write:
            target.parent.mkdir(parents=True, exist_ok=True)
            redirected[str(path.resolve())] = target
        return target

    def _resolve(path: Path, *, for_write: bool) -> Path:
        if not _is_mutable(path):
            return path
        key = str(path.resolve())
        if for_write:
            return _runtime_path(path, for_write=True)
        mapped = redirected.get(key)
        if mapped is not None and _ORIG_EXISTS(mapped):
            return mapped
        return path

    def _is_write_mode(mode: str) -> bool:
        return any(flag in mode for flag in ("w", "a", "x", "+"))

    def _open(self: Path, mode: str = "r", *args: Any, **kwargs: Any):  # type: ignore[override]
        if _is_mutable(self) and _is_write_mode(mode):
            target = _resolve(self, for_write=True)
            return _ORIG_OPEN(target, mode, *args, **kwargs)
        target = _resolve(self, for_write=False)
        return _ORIG_OPEN(target, mode, *args, **kwargs)

    def _write_text(self: Path, data: str, *args: Any, **kwargs: Any) -> int:  # type: ignore[override]
        target = _resolve(self, for_write=True) if _is_mutable(self) else self
        return _ORIG_WRITE_TEXT(target, data, *args, **kwargs)

    def _write_bytes(self: Path, data: bytes, *args: Any, **kwargs: Any) -> int:  # type: ignore[override]
        target = _resolve(self, for_write=True) if _is_mutable(self) else self
        return _ORIG_WRITE_BYTES(target, data, *args, **kwargs)

    def _read_text(self: Path, *args: Any, **kwargs: Any) -> str:  # type: ignore[override]
        target = _resolve(self, for_write=False)
        return _ORIG_READ_TEXT(target, *args, **kwargs)

    def _read_bytes(self: Path, *args: Any, **kwargs: Any) -> bytes:  # type: ignore[override]
        target = _resolve(self, for_write=False)
        return _ORIG_READ_BYTES(target, *args, **kwargs)

    def _exists(self: Path) -> bool:  # type: ignore[override]
        if _is_mutable(self):
            mapped = redirected.get(str(self.resolve()))
            if mapped is not None and _ORIG_EXISTS(mapped):
                return True
        return _ORIG_EXISTS(self)

    def _is_file(self: Path) -> bool:  # type: ignore[override]
        if _is_mutable(self):
            mapped = redirected.get(str(self.resolve()))
            if mapped is not None and _ORIG_IS_FILE(mapped):
                return True
        return _ORIG_IS_FILE(self)

    def _is_dir(self: Path) -> bool:  # type: ignore[override]
        if _is_mutable(self):
            mapped = redirected.get(str(self.resolve()))
            if mapped is not None and _ORIG_IS_DIR(mapped):
                return True
        return _ORIG_IS_DIR(self)

    def _mkdir(self: Path, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        target = _resolve(self, for_write=True) if _is_mutable(self) else self
        return _ORIG_MKDIR(target, *args, **kwargs)

    def _touch(self: Path, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        target = _resolve(self, for_write=True) if _is_mutable(self) else self
        return _ORIG_TOUCH(target, *args, **kwargs)

    def _unlink(self: Path, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        target = _resolve(self, for_write=False) if _is_mutable(self) else self
        if _ORIG_EXISTS(target):
            return _ORIG_UNLINK(target, *args, **kwargs)
        return _ORIG_UNLINK(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _open)
    monkeypatch.setattr(Path, "write_text", _write_text)
    monkeypatch.setattr(Path, "write_bytes", _write_bytes)
    monkeypatch.setattr(Path, "read_text", _read_text)
    monkeypatch.setattr(Path, "read_bytes", _read_bytes)
    monkeypatch.setattr(Path, "exists", _exists)
    monkeypatch.setattr(Path, "is_file", _is_file)
    monkeypatch.setattr(Path, "is_dir", _is_dir)
    monkeypatch.setattr(Path, "mkdir", _mkdir)
    monkeypatch.setattr(Path, "touch", _touch)
    monkeypatch.setattr(Path, "unlink", _unlink)
