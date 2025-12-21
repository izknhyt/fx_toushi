"""Merge market data files, update latest window, and refresh data manifest.

This utility consolidates per-symbol parquet/csv sources into a merged file,
cuts a rolling latest window, and optionally updates reports/data_manifest.json.
It also emits a simple gap report (missing 5m bars) to help plan backfills.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import subprocess


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
        "Datetime": "timestamp",
    }
    df = df.rename(columns=rename_map)
    required = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    df = df[required].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df["timestamp"] = df["timestamp"].dt.tz_convert(None)
    return df


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_sources(source_dir: Path) -> Iterable[Path]:
    for path in sorted(source_dir.glob("*.parquet")):
        name = path.name
        if name.endswith("_merged.parquet") or name.endswith("_latest.parquet"):
            continue
        yield path


def _load_sources(source_dir: Path, extra_csv: list[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in _iter_sources(source_dir):
        frames.append(_normalize_frame(pd.read_parquet(path)))
    for path in extra_csv:
        frames.append(_normalize_frame(pd.read_csv(path)))
    if not frames:
        raise SystemExit(f"no source data found in {source_dir}")
    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    return merged


def _cut_latest(df: pd.DataFrame, days: int) -> pd.DataFrame:
    if df.empty:
        return df
    end_ts = df["timestamp"].max()
    start_ts = end_ts - timedelta(days=days)
    return df[df["timestamp"] >= start_ts]


def _gap_report(
    df: pd.DataFrame,
    *,
    minutes: int = 5,
    weekend_exclude: bool = True,
) -> list[dict[str, str | int]]:
    if df.empty:
        return []
    ts = df["timestamp"].sort_values().to_list()
    gaps: list[dict[str, str | int]] = []
    expected = timedelta(minutes=minutes)
    for prev, curr in zip(ts, ts[1:]):
        delta = curr - prev
        if delta > expected:
            if weekend_exclude:
                # Skip gaps fully inside weekend (Sat/Sun UTC).
                if prev.weekday() >= 5 and curr.weekday() >= 5:
                    continue
            gaps.append(
                {
                    "from": prev.isoformat(),
                    "to": curr.isoformat(),
                    "gap_minutes": int(delta.total_seconds() // 60),
                }
            )
    return gaps


def _chunk_range(start: datetime, end: datetime, *, hours: int) -> Iterable[tuple[datetime, datetime]]:
    cursor = start
    step = timedelta(hours=hours)
    while cursor < end:
        chunk_end = min(cursor + step, end)
        yield cursor, chunk_end
        cursor = chunk_end


def _build_fetch_plan(
    gaps: list[dict[str, str | int]],
    *,
    symbol: str,
    out_dir: Path,
    chunk_hours: int,
) -> list[str]:
    commands: list[str] = []
    for gap in gaps:
        start = datetime.fromisoformat(str(gap["from"]))
        end = datetime.fromisoformat(str(gap["to"]))
        for chunk_start, chunk_end in _chunk_range(start, end, hours=chunk_hours):
            out_path = out_dir / f"{symbol.lower()}_m5_{chunk_start:%Y%m%d}_{chunk_end:%Y%m%d}_dukascopy.parquet"
            commands.append(
                "poetry run python tools/dukascopy_fetch.py "
                f"--pair {symbol} --from {chunk_start:%Y-%m-%d} --to {chunk_end:%Y-%m-%d} "
                f"--out {out_path}"
            )
    return commands


def _update_manifest(
    *,
    manifest_path: Path,
    symbol: str,
    merged_path: Path,
    window_from: str,
    window_to: str,
    dataset_sha: str,
) -> None:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    symbol_key = symbol.upper()
    for entry in payload.get("strategies", {}).values():
        watchlist = entry.get("watchlist_datasets") or {}
        if symbol_key in watchlist:
            watchlist[symbol_key]["path"] = str(merged_path)
            watchlist[symbol_key]["sha256"] = dataset_sha
        if str(merged_path).split("/")[-1].startswith(symbol_key.lower()):
            dataset_path = entry.get("dataset_path", "")
            if symbol_key.lower() in str(dataset_path):
                entry["dataset_path"] = str(merged_path)
                entry["dataset_sha256"] = dataset_sha
                entry["dataset_window"] = {"from": window_from, "to": window_to}
    payload["generated_at"] = _utcnow_iso()
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge market data and update manifests/latest files.")
    parser.add_argument("--symbol", required=True, help="Symbol, e.g. USDJPY")
    parser.add_argument("--source-dir", help="Directory holding per-symbol parquet files")
    parser.add_argument("--merged", help="Use an existing merged parquet instead of rebuilding")
    parser.add_argument("--extra-csv", action="append", default=[], help="Extra CSV inputs (repeatable)")
    parser.add_argument("--latest-days", type=int, default=30, help="Latest window length in days")
    parser.add_argument("--write-latest", action="store_true", help="Write *_m5_latest.parquet")
    parser.add_argument("--update-manifest", action="store_true", help="Update reports/data_manifest.json")
    parser.add_argument("--manifest", default="reports/data_manifest.json", help="Manifest path")
    parser.add_argument("--gap-report", help="Optional JSON gap report path")
    parser.add_argument("--gap-minutes", type=int, default=5, help="Gap threshold in minutes")
    parser.add_argument("--gap-exclude-weekend", action="store_true", help="Exclude weekend gaps")
    parser.add_argument("--emit-fetch-plan", help="Optional shell script path for backfill commands")
    parser.add_argument("--chunk-hours", type=int, default=6, help="Backfill chunk size in hours")
    parser.add_argument("--run-fetch-plan", action="store_true", help="Execute backfill commands sequentially")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    merged_path = Path(args.merged) if args.merged else None
    if merged_path is not None and not merged_path.exists():
        raise SystemExit(f"merged file not found: {merged_path}")

    source_dir = Path(args.source_dir or f"data/research/curated/{symbol.lower()}")
    extra_csv = [Path(path) for path in args.extra_csv]

    if merged_path is None:
        merged = _load_sources(source_dir, extra_csv)
        window_from = merged["timestamp"].min().strftime("%Y-%m-%d")
        window_to = merged["timestamp"].max().strftime("%Y-%m-%d")
        merged_path = source_dir / f"{symbol.lower()}_m5_{window_from.replace('-','')}_{window_to.replace('-','')}_merged.parquet"
        merged.to_parquet(merged_path, index=False)
    else:
        merged = _normalize_frame(pd.read_parquet(merged_path))
        window_from = merged["timestamp"].min().strftime("%Y-%m-%d")
        window_to = merged["timestamp"].max().strftime("%Y-%m-%d")
        source_dir = merged_path.parent

    if args.write_latest:
        latest = _cut_latest(merged, args.latest_days)
        latest_path = source_dir / f"{symbol.lower()}_m5_latest.parquet"
        latest.to_parquet(latest_path, index=False)

    dataset_sha = _sha256(merged_path)
    if args.update_manifest:
        _update_manifest(
            manifest_path=Path(args.manifest),
            symbol=symbol,
            merged_path=merged_path,
            window_from=window_from,
            window_to=window_to,
            dataset_sha=dataset_sha,
        )

    gaps: list[dict[str, str | int]] | None = None
    if args.gap_report:
        gaps = _gap_report(
            merged,
            minutes=args.gap_minutes,
            weekend_exclude=args.gap_exclude_weekend,
        )
        report_path = Path(args.gap_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(gaps, ensure_ascii=False, indent=2), encoding="utf-8")

    commands: list[str] = []
    if args.emit_fetch_plan:
        if gaps is None:
            gaps = _gap_report(
                merged,
                minutes=args.gap_minutes,
                weekend_exclude=args.gap_exclude_weekend,
            )
        plan_path = Path(args.emit_fetch_plan)
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        commands = _build_fetch_plan(
            gaps,
            symbol=symbol,
            out_dir=source_dir,
            chunk_hours=args.chunk_hours,
        )
        content = "#!/usr/bin/env bash\nset -euo pipefail\n\n"
        content += "\n".join(commands) + "\n"
        plan_path.write_text(content, encoding="utf-8")

    if args.run_fetch_plan:
        if not commands:
            if gaps is None:
                gaps = _gap_report(
                    merged,
                    minutes=args.gap_minutes,
                    weekend_exclude=args.gap_exclude_weekend,
                )
            commands = _build_fetch_plan(
                gaps,
                symbol=symbol,
                out_dir=source_dir,
                chunk_hours=args.chunk_hours,
            )
        for cmd in commands:
            subprocess.run(cmd, shell=True, check=True)

    print(json.dumps({"symbol": symbol, "merged": str(merged_path), "sha256": dataset_sha}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
