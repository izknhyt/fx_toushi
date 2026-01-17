"""Benchmark ingestion and manual validation helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DEFAULT_RAW_DIR = Path("benchmark_runs/raw")
DEFAULT_SIGNOFF_DIR = Path("reports/benchmark/manual_log_signoff")


class BenchmarkIngestError(RuntimeError):
    """Raised when benchmark ingestion fails validation."""


class BenchmarkManualValidationError(RuntimeError):
    """Raised when manual benchmark validation fails."""

    def __init__(self, message: str, *, exit_code: int = 120) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(slots=True)
class BenchmarkIngestResult:
    provider: str
    mode: str
    symbol: str | None
    timeframe: str | None
    rows: int
    duplicates_dropped: int
    missing_filled: int
    output_path: Path | None
    status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "mode": self.mode,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "rows": self.rows,
            "duplicates_dropped": self.duplicates_dropped,
            "missing_filled": self.missing_filled,
            "output_path": str(self.output_path) if self.output_path else None,
            "status": self.status,
        }


def _parse_timeframe(value: str | None) -> str | None:
    if not value:
        return None
    token = value.strip().lower()
    try:
        if token.endswith("m"):
            return f"{int(token[:-1])}min"
        if token.endswith("h"):
            return f"{int(token[:-1])}h"
        if token.endswith("d"):
            return f"{int(token[:-1])}d"
        if token.endswith("w"):
            return f"{int(token[:-1])}w"
    except ValueError:
        return None
    return None


def _load_frame(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    candidates = [col for col in frame.columns if col.lower() in {"ts", "time", "timestamp", "date", "datetime"}]
    if not candidates:
        raise BenchmarkIngestError("timestamp column is required")
    ts_col = candidates[0]
    normalized = frame.copy()
    normalized["ts"] = pd.to_datetime(normalized[ts_col], utc=True, errors="coerce")
    normalized = normalized.dropna(subset=["ts"])
    close_candidates = [col for col in normalized.columns if col.lower() in {"close", "c", "price"}]
    if not close_candidates:
        raise BenchmarkIngestError("close/price column is required")
    close_col = close_candidates[0]
    normalized["close"] = pd.to_numeric(normalized[close_col], errors="coerce")
    for col in ("open", "high", "low"):
        if col not in normalized.columns:
            normalized[col] = normalized["close"]
    return normalized[["ts", "open", "high", "low", "close"]]


def _fill_missing(frame: pd.DataFrame, *, freq: str | None) -> tuple[pd.DataFrame, int]:
    if frame.empty or not freq:
        return frame, 0
    index = pd.date_range(frame["ts"].min(), frame["ts"].max(), freq=freq, tz=timezone.utc)
    before = len(frame)
    reindexed = frame.set_index("ts").reindex(index)
    missing = len(reindexed) - before
    reindexed["close"] = reindexed["close"].ffill()
    for col in ("open", "high", "low"):
        reindexed[col] = reindexed[col].fillna(reindexed["close"])
    reindexed = reindexed.reset_index().rename(columns={"index": "ts"})
    return reindexed, max(missing, 0)


class BenchmarkIngestor:
    def __init__(self, *, output_dir: Path = DEFAULT_RAW_DIR) -> None:
        self._output_dir = output_dir

    def ingest(
        self,
        *,
        provider: str,
        path: Path,
        mode: str,
        symbol: str | None = None,
        timeframe: str | None = None,
        validate_only: bool = False,
    ) -> BenchmarkIngestResult:
        raw = _load_frame(path)
        normalized = _normalize_frame(raw)
        duplicates = int(normalized["ts"].duplicated().sum())
        normalized = normalized.drop_duplicates(subset=["ts"], keep="last").sort_values("ts")
        freq = _parse_timeframe(timeframe)
        normalized, missing_filled = _fill_missing(normalized, freq=freq)
        output_path = None
        status = "ok"
        if not validate_only:
            stamped = datetime.now(timezone.utc).strftime("%Y%m%d")
            out_dir = self._output_dir / provider
            out_dir.mkdir(parents=True, exist_ok=True)
            suffix = _output_suffix(symbol=symbol, timeframe=timeframe, mode=mode)
            output_path = out_dir / f"{stamped}{suffix}.parquet"
            normalized.to_parquet(output_path, index=False)
        return BenchmarkIngestResult(
            provider=provider,
            mode=mode,
            symbol=symbol,
            timeframe=timeframe,
            rows=len(normalized),
            duplicates_dropped=duplicates,
            missing_filled=missing_filled,
            output_path=output_path,
            status=status,
        )


def validate_manual(path: Path) -> dict[str, object]:
    directory = path if path.is_dir() else path.parent
    pairs = _pair_manual_files(directory)
    if not pairs:
        raise BenchmarkManualValidationError("manual files (_op.csv/_review.csv) not found")
    op_file, review_file = pairs[0]
    op_frame = _normalize_frame(_load_frame(op_file)).sort_values("ts").reset_index(drop=True)
    review_frame = _normalize_frame(_load_frame(review_file)).sort_values("ts").reset_index(drop=True)
    if len(op_frame) != len(review_frame):
        raise BenchmarkManualValidationError("manual files have different row counts")
    diff = (op_frame[["ts", "open", "high", "low", "close"]].round(6) !=
            review_frame[["ts", "open", "high", "low", "close"]].round(6)).any(axis=None)
    if diff:
        raise BenchmarkManualValidationError("manual files do not match")
    stamped = datetime.now(timezone.utc).strftime("%Y%m%d")
    output_dir = DEFAULT_RAW_DIR / "manual"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{stamped}.parquet"
    op_frame.to_parquet(output_path, index=False)
    signoff_dir = DEFAULT_SIGNOFF_DIR
    signoff_dir.mkdir(parents=True, exist_ok=True)
    signoff_path = signoff_dir / f"{stamped}.md"
    op_hash = hashlib.sha256(op_file.read_bytes()).hexdigest()
    review_hash = hashlib.sha256(review_file.read_bytes()).hexdigest()
    signoff_path.write_text(
        "\n".join(
            [
                "# Benchmark Manual Validation Signoff",
                f"- ts: {datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}",
                f"- op_file: {op_file}",
                f"- review_file: {review_file}",
                f"- op_sha256: {op_hash}",
                f"- review_sha256: {review_hash}",
                f"- output: {output_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "status": "ok",
        "op_file": str(op_file),
        "review_file": str(review_file),
        "output_path": str(output_path),
        "signoff_path": str(signoff_path),
    }


def _output_suffix(*, symbol: str | None, timeframe: str | None, mode: str | None) -> str:
    parts: list[str] = []
    if symbol:
        parts.append(symbol.lower())
    if timeframe:
        parsed = _parse_timeframe(timeframe)
        if parsed:
            parts.append(parsed)
    if mode:
        parts.append(mode)
    if not parts:
        return ""
    return "_" + "_".join(parts)


def _pair_manual_files(directory: Path) -> list[tuple[Path, Path]]:
    op_files = sorted(directory.glob("*_op.csv"))
    review_files = {
        path.name.replace("_review.csv", ""): path
        for path in directory.glob("*_review.csv")
    }
    pairs: list[tuple[Path, Path]] = []
    for op_file in op_files:
        base = op_file.name.replace("_op.csv", "")
        review_file = review_files.get(base)
        if review_file:
            pairs.append((op_file, review_file))
    return pairs
