"""Paid feed provider adapter using local parquet/CSV sources."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from ..service import MarketFrame, MarketRequest
from .base import ProviderAdapter

__all__ = ["PaidFeedProvider"]

DEFAULT_PAID_FEED_CONFIG = Path("config/data_sources/paid_feed.yaml")
DEFAULT_PAID_FEED_PATH = Path("data/paid_feed/paid_feed.parquet")


@dataclass(slots=True)
class PaidFeedProvider(ProviderAdapter):  # type: ignore[misc]
    """Adapter that loads paid feed bars from local storage."""

    name: str = "paid_feed"
    source_path: Path | None = None
    timeout_sec: float | None = None
    config_path: Path = DEFAULT_PAID_FEED_CONFIG

    def fetch_bars(self, request: MarketRequest) -> list[MarketFrame]:
        path = self.source_path or _resolve_paid_feed_path(self.config_path)
        frame = _load_paid_feed(path)
        if frame.empty:
            return [MarketFrame(symbol=symbol, timeframe=request.timeframe, bars=[]) for symbol in request.symbols]

        start = _parse_time(request.start)
        end = _parse_time(request.end)
        if start is not None:
            frame = frame[frame["timestamp"] >= start]
        if end is not None:
            frame = frame[frame["timestamp"] <= end]

        frames: list[MarketFrame] = []
        for symbol in request.symbols:
            symbol_frame = frame[frame["symbol"] == symbol.upper()]
            rows = _frame_to_rows(symbol_frame)
            frames.append(MarketFrame(symbol=symbol, timeframe=request.timeframe, bars=rows))
        return frames


def _resolve_paid_feed_path(config_path: Path) -> Path:
    env_path = os.getenv("TRADECTL_PAID_FEED_PATH")
    if env_path:
        return Path(env_path)
    if config_path.exists():
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if isinstance(payload, dict):
            endpoint = payload.get("endpoint")
            if isinstance(endpoint, str) and endpoint:
                if endpoint.startswith("file://"):
                    return Path(endpoint[len("file://") :])
                return Path(endpoint)
    return DEFAULT_PAID_FEED_PATH


def _load_paid_feed(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)
    if "symbol" not in frame.columns:
        return pd.DataFrame()
    ts_col = "ts" if "ts" in frame.columns else "timestamp" if "timestamp" in frame.columns else None
    if ts_col is None:
        return pd.DataFrame()
    frame["timestamp"] = pd.to_datetime(frame[ts_col], utc=True, errors="coerce")
    frame = frame.dropna(subset=["timestamp"])
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    return frame


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


def _frame_to_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        ts = row.get("timestamp")
        if pd.isna(ts):
            continue
        rows.append(
            {
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
        )
    return rows
