"""GUI one-click data sync helpers."""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class GuiDataSyncError(RuntimeError):
    """Raised when one-click data sync fails."""


class GuiDataSyncStopped(RuntimeError):
    """Raised when one-click data sync is stopped by user request."""


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
    warnings: list[str]
    backfill_duration_sec: int
    refresh_duration_sec: int
    total_duration_sec: int

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
            "warnings": list(self.warnings),
            "backfill_duration_sec": self.backfill_duration_sec,
            "refresh_duration_sec": self.refresh_duration_sec,
            "total_duration_sec": self.total_duration_sec,
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


def _is_no_data_failure(stderr: str, stdout: str) -> bool:
    blob = f"{stderr}\n{stdout}".lower()
    return "no data fetched; nothing to write" in blob


def _should_stop(should_stop: Callable[[], bool] | None) -> bool:
    if should_stop is None:
        return False
    try:
        return bool(should_stop())
    except Exception:
        return False


def _terminate_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)


def _run_command(
    command: list[str],
    *,
    allow_no_data: bool = False,
    should_stop: Callable[[], bool] | None = None,
) -> tuple[str, list[str]]:
    if _should_stop(should_stop):
        raise GuiDataSyncStopped("sync stopped by user")

    if should_stop is None:
        try:
            proc = subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            if allow_no_data and _is_no_data_failure(stderr, stdout):
                detail = stderr or stdout or "no data fetched; nothing to write"
                return detail, ["no_data_fetched_during_backfill"]
            detail = stderr or stdout or f"exit_code={exc.returncode}"
            raise GuiDataSyncError(
                f"command failed: {' '.join(command)} :: {detail}"
            ) from exc
        return (proc.stdout or "").strip(), []

    proc = subprocess.Popen(  # noqa: S603
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    while proc.poll() is None:
        if _should_stop(should_stop):
            _terminate_process(proc)
            raise GuiDataSyncStopped("sync stopped by user")
        time.sleep(0.2)

    stdout_raw, stderr_raw = proc.communicate()
    stdout = (stdout_raw or "").strip()
    stderr = (stderr_raw or "").strip()
    if proc.returncode == 0:
        return stdout, []
    if allow_no_data and _is_no_data_failure(stderr, stdout):
        detail = stderr or stdout or "no data fetched; nothing to write"
        return detail, ["no_data_fetched_during_backfill"]
    detail = stderr or stdout or f"exit_code={proc.returncode}"
    raise GuiDataSyncError(f"command failed: {' '.join(command)} :: {detail}")


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
    progress_hook: Callable[[str, Mapping[str, Any]], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
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

    total_started = time.perf_counter()
    if progress_hook is not None:
        progress_hook("sync.backfill.start", {"step": 1, "total_steps": 2, "progress_pct": 10})
    backfill_started = time.perf_counter()
    backfill_stdout, backfill_warnings = _run_command(
        backfill_cmd, allow_no_data=run_fetch_plan, should_stop=should_stop
    )
    backfill_duration_sec = int(max(0.0, time.perf_counter() - backfill_started))
    if progress_hook is not None:
        progress_hook(
            "sync.backfill.done",
            {
                "step": 1,
                "total_steps": 2,
                "progress_pct": 55,
                "duration_sec": backfill_duration_sec,
            },
        )

    if progress_hook is not None:
        progress_hook("sync.refresh.start", {"step": 2, "total_steps": 2, "progress_pct": 60})
    refresh_started = time.perf_counter()
    refresh_stdout, refresh_warnings = _run_command(refresh_cmd, should_stop=should_stop)
    refresh_duration_sec = int(max(0.0, time.perf_counter() - refresh_started))
    total_duration_sec = int(max(0.0, time.perf_counter() - total_started))
    if progress_hook is not None:
        progress_hook(
            "sync.refresh.done",
            {
                "step": 2,
                "total_steps": 2,
                "progress_pct": 95,
                "duration_sec": refresh_duration_sec,
                "total_duration_sec": total_duration_sec,
            },
        )

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
        warnings=[*backfill_warnings, *refresh_warnings],
        backfill_duration_sec=backfill_duration_sec,
        refresh_duration_sec=refresh_duration_sec,
        total_duration_sec=total_duration_sec,
    )


__all__ = [
    "GuiDataSyncError",
    "GuiDataSyncStopped",
    "GuiDataSyncResult",
    "build_gui_data_sync_commands",
    "run_gui_data_sync",
]
