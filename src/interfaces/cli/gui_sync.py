"""GUI one-click data sync helpers."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class GuiDataSyncError(RuntimeError):
    """Raised when one-click data sync fails."""


@dataclass(frozen=True)
class GuiDataSyncResult:
    symbol: str
    source_dir: Path
    manifest: Path
    gap_report_before: Path
    gap_report_after: Path
    fetch_plan: Path
    backfill_command: list[str]
    refresh_command: list[str]
    backfill_stdout: str
    refresh_stdout: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "source_dir": str(self.source_dir),
            "manifest": str(self.manifest),
            "gap_report_before": str(self.gap_report_before),
            "gap_report_after": str(self.gap_report_after),
            "fetch_plan": str(self.fetch_plan),
            "backfill_command": " ".join(self.backfill_command),
            "refresh_command": " ".join(self.refresh_command),
            "backfill_stdout": self.backfill_stdout,
            "refresh_stdout": self.refresh_stdout,
        }


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")


def build_gui_data_sync_commands(
    *,
    symbol: str,
    source_dir: Path,
    manifest: Path,
    validation_dir: Path,
    latest_days: int,
    gap_minutes: int,
    chunk_hours: int,
    gap_exclude_weekend: bool,
    run_fetch_plan: bool,
    stamp: str | None = None,
) -> tuple[list[str], list[str], dict[str, Path]]:
    stamp_value = stamp or _utc_stamp()
    symbol_key = symbol.upper()
    symbol_lower = symbol_key.lower()
    validation_dir.mkdir(parents=True, exist_ok=True)

    gap_before = validation_dir / f"{symbol_lower}_gap_before_{stamp_value}.json"
    gap_after = validation_dir / f"{symbol_lower}_gap_after_{stamp_value}.json"
    fetch_plan = validation_dir / f"{symbol_lower}_backfill_{stamp_value}.sh"

    base = [
        sys.executable,
        "tools/update_market_data.py",
        "--symbol",
        symbol_key,
        "--source-dir",
        str(source_dir),
        "--gap-minutes",
        str(gap_minutes),
        "--chunk-hours",
        str(chunk_hours),
    ]
    if gap_exclude_weekend:
        base.append("--gap-exclude-weekend")

    backfill_cmd = [
        *base,
        "--gap-report",
        str(gap_before),
        "--emit-fetch-plan",
        str(fetch_plan),
    ]
    if run_fetch_plan:
        backfill_cmd.append("--run-fetch-plan")

    refresh_cmd = [
        *base,
        "--gap-report",
        str(gap_after),
        "--write-latest",
        "--latest-days",
        str(latest_days),
        "--update-manifest",
        "--manifest",
        str(manifest),
    ]

    paths = {
        "gap_report_before": gap_before,
        "gap_report_after": gap_after,
        "fetch_plan": fetch_plan,
    }
    return backfill_cmd, refresh_cmd, paths


def _run_command(command: list[str]) -> str:
    try:
        proc = subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or f"exit_code={exc.returncode}"
        raise GuiDataSyncError(
            f"command failed: {' '.join(command)} :: {detail}"
        ) from exc
    return (proc.stdout or "").strip()


def run_gui_data_sync(
    *,
    symbol: str,
    source_dir: Path,
    manifest: Path,
    validation_dir: Path,
    latest_days: int,
    gap_minutes: int,
    chunk_hours: int,
    gap_exclude_weekend: bool,
    run_fetch_plan: bool,
) -> GuiDataSyncResult:
    backfill_cmd, refresh_cmd, paths = build_gui_data_sync_commands(
        symbol=symbol,
        source_dir=source_dir,
        manifest=manifest,
        validation_dir=validation_dir,
        latest_days=latest_days,
        gap_minutes=gap_minutes,
        chunk_hours=chunk_hours,
        gap_exclude_weekend=gap_exclude_weekend,
        run_fetch_plan=run_fetch_plan,
    )

    backfill_stdout = _run_command(backfill_cmd)
    refresh_stdout = _run_command(refresh_cmd)

    return GuiDataSyncResult(
        symbol=symbol.upper(),
        source_dir=source_dir,
        manifest=manifest,
        gap_report_before=paths["gap_report_before"],
        gap_report_after=paths["gap_report_after"],
        fetch_plan=paths["fetch_plan"],
        backfill_command=backfill_cmd,
        refresh_command=refresh_cmd,
        backfill_stdout=backfill_stdout,
        refresh_stdout=refresh_stdout,
    )


__all__ = [
    "GuiDataSyncError",
    "GuiDataSyncResult",
    "build_gui_data_sync_commands",
    "run_gui_data_sync",
]
