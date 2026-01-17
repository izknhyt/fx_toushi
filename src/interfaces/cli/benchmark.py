"""Stub for `tradectl benchmark` commands (see §17.10)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.benchmark import (
    BenchmarkComparisonResult,
    BenchmarkIngestError,
    BenchmarkIngestResult,
    BenchmarkIngestor,
    BenchmarkManualValidationError,
    BenchmarkReplayGapError,
    BenchmarkReplayService,
    validate_manual as run_manual_validation,
)
from src.reporter.benchmark import BenchmarkGapError

logger = logging.getLogger(__name__)

__all__ = [
    "ingest",
    "compare",
    "validate_manual",
    "BenchmarkGapError",
    "BenchmarkReplayGapError",
]


def ingest(
    *,
    provider: str,
    file: str,
    mode: str,
    symbol: str | None = None,
    email: str | None = None,
    timeframe: str | None = None,
    validate_only: bool = False,
) -> BenchmarkIngestResult:
    """Ingest benchmark feeds from CSV/Parquet."""

    ingestor = BenchmarkIngestor()
    try:
        result = ingestor.ingest(
            provider=provider,
            path=Path(file),
            mode=mode,
            symbol=symbol,
            timeframe=timeframe,
            validate_only=validate_only,
        )
    except BenchmarkIngestError as exc:
        logger.error(
            "cli.benchmark.ingest.failed",
            extra={"provider": provider, "file": file, "mode": mode, "error": str(exc)},
        )
        raise
    logger.info(
        "cli.benchmark.ingest.completed",
        extra={**result.to_dict(), "file": file, "email": email},
    )
    return result


def compare(
    *,
    window: str,
    mode: str,
    providers: list[str] | None = None,
    export_md: str | None = None,
    export_json: str | None = None,
    fail_on_gap: bool = False,
) -> BenchmarkComparisonResult:
    """Compare benchmark data against strategy performance."""
    try:
        result = BenchmarkReplayService().replay(
            window=window,
            mode=mode,
            providers=providers,
            export_path=Path(export_md) if export_md else None,
            fail_on_gap=fail_on_gap,
        )
    except BenchmarkReplayGapError as exc:
        result = exc.result
        if fail_on_gap:
            raise
    if export_json:
        export_path = Path(export_json)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    logger.info(
        "cli.benchmark.compare.completed",
        extra={
            "window": window,
            "mode": mode,
            "providers": providers or [],
            "export_md": export_md,
            "export_json": export_json,
            "status": result.status,
            "missing_ratio": result.missing_ratio,
        },
    )
    return result


def validate_manual(path: str) -> dict[str, object]:
    """Validate manual benchmark CSV files."""

    try:
        payload = run_manual_validation(Path(path))
    except BenchmarkManualValidationError as exc:
        logger.error("cli.benchmark.validate_manual.failed", extra={"path": path, "error": str(exc)})
        raise
    logger.info("cli.benchmark.validate_manual.completed", extra=payload)
    return payload
