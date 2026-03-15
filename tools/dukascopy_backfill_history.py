"""Plan and execute long-range Dukascopy backfills to extend history backwards.

Typical usage:
    poetry run python tools/dukascopy_backfill_history.py \
        --symbol USDJPY \
        --target-start 2016-01-01 \
        --existing-merged data/research/curated/usdjpy/usdjpy_m5_20210101_20260225_merged.parquet \
        --chunk-days 14 \
        --plan-json reports/validation_log/usdjpy_2016_backfill_plan.json

    poetry run python tools/dukascopy_backfill_history.py \
        --symbol USDJPY \
        --target-start 2016-01-01 \
        --existing-merged data/research/curated/usdjpy/usdjpy_m5_20210101_20260225_merged.parquet \
        --chunk-days 14 \
        --run \
        --merge-after
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class BackfillChunk:
    start: str
    end: str
    out_path: str
    exists: bool


def resolve_existing_merged(symbol: str, explicit_path: Path | None = None) -> Path:
    if explicit_path is not None:
        if not explicit_path.exists():
            raise FileNotFoundError(f"existing merged file not found: {explicit_path}")
        return explicit_path.resolve()

    symbol_dir = Path("data") / "research" / "curated" / symbol.lower()
    candidates = sorted(
        symbol_dir.glob(f"{symbol.lower()}_m5_*_merged.parquet"),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        raise FileNotFoundError(f"no merged parquet found under {symbol_dir}")
    return candidates[-1].resolve()


def load_merged_start_date(path: Path) -> date:
    df = pd.read_parquet(path, columns=["timestamp"])
    ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").dropna()
    if ts.empty:
        raise ValueError(f"merged parquet has no valid timestamps: {path}")
    return ts.min().date()


def build_history_extension_chunks(
    *,
    symbol: str,
    target_start: date,
    existing_start: date,
    out_dir: Path,
    chunk_days: int,
) -> list[BackfillChunk]:
    if chunk_days <= 0:
        raise ValueError("chunk_days must be positive")
    fetch_end = existing_start - timedelta(days=1)
    if target_start > fetch_end:
        return []

    chunks: list[BackfillChunk] = []
    cursor = target_start
    step = timedelta(days=chunk_days - 1)
    while cursor <= fetch_end:
        chunk_end = min(cursor + step, fetch_end)
        out_path = out_dir / (
            f"{symbol.lower()}_m5_{cursor:%Y%m%d}_{chunk_end:%Y%m%d}_dukascopy.parquet"
        )
        chunks.append(
            BackfillChunk(
                start=cursor.isoformat(),
                end=chunk_end.isoformat(),
                out_path=str(out_path),
                exists=out_path.exists(),
            )
        )
        cursor = chunk_end + timedelta(days=1)
    return chunks


def run_fetch_chunk(symbol: str, chunk: BackfillChunk, *, fetch_workers: int) -> None:
    subprocess.run(
        [
            sys.executable,
            "tools/dukascopy_fetch.py",
            "--pair",
            symbol,
            "--from",
            chunk.start,
            "--to",
            chunk.end,
            "--out",
            chunk.out_path,
            "--workers",
            str(fetch_workers),
        ],
        check=True,
    )


def run_merge(symbol: str, source_dir: Path, *, latest_days: int, update_manifest: bool) -> None:
    cmd = [
        sys.executable,
        "tools/update_market_data.py",
        "--symbol",
        symbol,
        "--source-dir",
        str(source_dir),
        "--write-latest",
        "--latest-days",
        str(latest_days),
    ]
    if update_manifest:
        cmd.append("--update-manifest")
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extend an existing merged history backwards with Dukascopy chunks."
    )
    parser.add_argument("--symbol", default="USDJPY", help="FX symbol, e.g. USDJPY")
    parser.add_argument(
        "--target-start",
        required=True,
        help="Desired earliest date in merged history (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--existing-merged",
        help="Existing merged parquet path. Defaults to newest *_merged.parquet for the symbol.",
    )
    parser.add_argument(
        "--out-dir",
        help="Output directory for fetched parquet chunks. Defaults to data/research/curated/<symbol>",
    )
    parser.add_argument("--chunk-days", type=int, default=14, help="Chunk size in calendar days")
    parser.add_argument(
        "--limit-chunks",
        type=int,
        default=0,
        help="Optional cap on chunks to execute (0 means all planned chunks).",
    )
    parser.add_argument("--plan-json", help="Optional JSON output path for the generated plan")
    parser.add_argument("--run", action="store_true", help="Execute the planned backfill chunks")
    parser.add_argument(
        "--fetch-workers",
        type=int,
        default=6,
        help="Hourly fetch worker count passed through to dukascopy_fetch.py",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not skip already-existing output parquet chunks",
    )
    parser.add_argument(
        "--merge-after",
        action="store_true",
        help="Run tools/update_market_data.py after chunk execution",
    )
    parser.add_argument(
        "--latest-days",
        type=int,
        default=120,
        help="Days to keep in *_m5_latest.parquet when merging after fetch",
    )
    parser.add_argument(
        "--no-update-manifest",
        action="store_true",
        help="Do not refresh reports/data_manifest.json during merge-after",
    )
    args = parser.parse_args()

    symbol = args.symbol.upper().strip()
    target_start = date.fromisoformat(args.target_start)
    existing_merged = resolve_existing_merged(
        symbol, Path(args.existing_merged) if args.existing_merged else None
    )
    existing_start = load_merged_start_date(existing_merged)
    out_dir = Path(args.out_dir) if args.out_dir else existing_merged.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    chunks = build_history_extension_chunks(
        symbol=symbol,
        target_start=target_start,
        existing_start=existing_start,
        out_dir=out_dir,
        chunk_days=args.chunk_days,
    )
    planned_chunks = chunks
    if not args.no_resume:
        chunks = [chunk for chunk in chunks if not chunk.exists]
    if args.limit_chunks > 0:
        chunks = chunks[: args.limit_chunks]

    payload = {
        "symbol": symbol,
        "target_start": target_start.isoformat(),
        "existing_merged": str(existing_merged),
        "existing_start": existing_start.isoformat(),
        "fetch_until": (existing_start - timedelta(days=1)).isoformat(),
        "chunk_days": args.chunk_days,
        "planned_chunk_count": len(planned_chunks),
        "existing_chunk_count": sum(1 for chunk in planned_chunks if chunk.exists),
        "remaining_chunk_count": len(chunks),
        "chunks": [asdict(chunk) for chunk in planned_chunks],
    }

    if args.plan_json:
        plan_path = Path(args.plan_json)
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.run:
        for index, chunk in enumerate(chunks, start=1):
            sys.stdout.write(
                f"[{index}/{len(chunks)}] fetching {chunk.start}..{chunk.end} -> {chunk.out_path}\n"
            )
            run_fetch_chunk(symbol, chunk, fetch_workers=max(int(args.fetch_workers), 1))
        if args.merge_after:
            run_merge(
                symbol,
                out_dir,
                latest_days=args.latest_days,
                update_manifest=not args.no_update_manifest,
            )

    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
