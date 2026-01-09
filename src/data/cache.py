"""Simple parquet cache helper referenced by §1.3."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CacheEntry:
    """Metadata describing a cached artifact."""

    path: Path
    rows: int
    columns: int


class DataCache:
    """Light-weight parquet cache that mirrors the design contract."""

    def __init__(self, root: str | Path = "data/cache") -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def resolve(self, key: str) -> Path:
        return self._root / f"{key}.parquet"

    def exists(self, key: str) -> bool:
        return self.resolve(key).exists()

    def store(self, key: str, frame: pd.DataFrame) -> CacheEntry:
        path = self.resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path)
        entry = CacheEntry(path=path, rows=len(frame.index), columns=len(frame.columns))
        logger.info(
            "data.cache.store", extra={"key": key, "rows": entry.rows, "columns": entry.columns}
        )
        return entry

    def load(self, key: str, columns: Iterable[str] | None = None) -> pd.DataFrame:
        path = self.resolve(key)
        if not path.exists():
            raise FileNotFoundError(path)
        frame = pd.read_parquet(path, columns=list(columns) if columns else None)
        logger.debug("data.cache.load", extra={"key": key, "rows": len(frame.index)})
        return frame


__all__ = ["CacheEntry", "DataCache"]
