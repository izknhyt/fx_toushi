"""Manual CSV loader provider implementation."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..service import MarketFrame, MarketRequest
from .base import ProviderAdapter

__all__ = ["CsvLoaderProvider", "FakeCsvLoader"]


@dataclass(slots=True)
class CsvLoaderProvider(ProviderAdapter):  # type: ignore[misc]
    """Adapter that loads bars from manual CSV submissions."""

    name: str = "manual_csv"
    root: Path = Path("data/manual_fallback")

    def fetch_bars(self, request: MarketRequest) -> Iterable[MarketFrame]:
        start = _parse_time(request.start)
        end = _parse_time(request.end)
        frames: list[MarketFrame] = []
        for symbol in request.symbols:
            rows = _load_symbol_rows(self.root, symbol, start=start, end=end)
            frames.append(MarketFrame(symbol=symbol, timeframe=request.timeframe, bars=rows))
        return frames


class FakeCsvLoader(CsvLoaderProvider):
    """Configurable CSV loader for tests."""

    def __init__(
        self,
        frames: Sequence[MarketFrame] | None = None,
        *,
        root: Path | None = None,
    ) -> None:
        super().__init__(root=root or Path("/tmp/manual"))
        self._frames = list(frames) if frames is not None else []

    def fetch_bars(self, request: MarketRequest) -> Iterator[MarketFrame]:
        if self._frames:
            return iter(self._frames)
        return iter(super().fetch_bars(request))


def _parse_time(raw: str | None) -> pd.Timestamp | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        ts = pd.Timestamp(text)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts


def _load_symbol_rows(
    root: Path, symbol: str, *, start: pd.Timestamp | None, end: pd.Timestamp | None
) -> list[dict[str, object]]:
    symbol_name = symbol.upper()
    provider_dirs = list(root.iterdir()) if root.exists() else []
    op_files: list[Path] = []
    for provider_dir in provider_dirs:
        if not provider_dir.is_dir():
            continue
        symbol_dir = provider_dir / symbol_name
        if not symbol_dir.exists():
            continue
        op_files.extend(symbol_dir.rglob("*_op.csv"))
    op_files = sorted(op_files)
    rows: list[dict[str, object]] = []
    for op_file in op_files:
        review_file = op_file.with_name(op_file.name.replace("_op.csv", "_review.csv"))
        if not review_file.exists():
            continue
        if _hash_file(op_file) != _hash_file(review_file):
            continue
        frame = _load_csv(op_file)
        if frame.empty:
            continue
        if start is not None:
            frame = frame[frame["timestamp"] >= start]
        if end is not None:
            frame = frame[frame["timestamp"] <= end]
        rows.extend(_frame_to_rows(frame))
    return rows


def _load_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    ts_col = (
        "ts" if "ts" in frame.columns else "timestamp" if "timestamp" in frame.columns else None
    )
    if ts_col is None:
        return pd.DataFrame()
    frame["timestamp"] = pd.to_datetime(frame[ts_col], utc=True, errors="coerce")
    frame = frame.dropna(subset=["timestamp"])
    return frame


def _frame_to_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        ts = row.get("timestamp")
        if pd.isna(ts):
            continue
        payload = {
            "timestamp": pd.Timestamp(ts)
            .to_pydatetime()
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "open": float(row.get("open", 0.0)),
            "high": float(row.get("high", 0.0)),
            "low": float(row.get("low", 0.0)),
            "close": float(row.get("close", 0.0)),
            "volume": float(row.get("volume", 0.0)),
        }
        if "spread" in row:
            payload["spread"] = float(row.get("spread", 0.0))
        if "session_tag" in row:
            payload["session_tag"] = row.get("session_tag")
        rows.append(payload)
    return rows


def _hash_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()
