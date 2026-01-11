"""Stub for `tradectl benchmark` commands (see §17.10)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.reporter.benchmark import BenchmarkComparator, BenchmarkGapError, BenchmarkResult

logger = logging.getLogger(__name__)

__all__ = ["ingest", "compare", "validate_manual", "BenchmarkGapError"]


def ingest(
    *,
    provider: str,
    file: str,
    mode: str,
    symbol: str | None = None,
    email: str | None = None,
) -> None:
    """Stub for benchmark ingestion."""

    logger.info(
        "cli.benchmark.ingest.stub",
        extra={"provider": provider, "file": file, "mode": mode, "symbol": symbol, "email": email},
    )
    raise NotImplementedError("tradectl benchmark ingest is not implemented in the M1 scaffold")


def compare(
    *,
    window: str,
    mode: str,
    providers: list[str] | None = None,
    export: str | None = None,
    fail_on_gap: bool = False,
) -> BenchmarkResult:
    """Compare benchmark data against strategy performance."""
    comparator = BenchmarkComparator()
    try:
        result = comparator.compare(window=window, mode=mode, providers=providers)
    except BenchmarkGapError as exc:
        result = exc.result
        if fail_on_gap:
            raise
    if export:
        export_path = Path(export)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        result.export_path = str(export_path)
    logger.info(
        "cli.benchmark.compare.completed",
        extra={
            "window": window,
            "mode": mode,
            "providers": providers or [],
            "export": export,
            "status": result.status,
            "missing_ratio": result.missing_ratio,
        },
    )
    return result


def validate_manual(path: str) -> None:
    """Stub for validating manual benchmark CSV files."""

    logger.info("cli.benchmark.validate_manual.stub", extra={"path": path})
    raise NotImplementedError(
        "tradectl benchmark validate-manual is not implemented in the M1 scaffold"
    )
