from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.interfaces.cli.gui_sync import (
    GuiDataSyncStopped,
    build_gui_data_sync_commands,
    run_gui_data_sync,
)


def test_build_gui_data_sync_commands_includes_required_flags(tmp_path: Path) -> None:
    source_dir = tmp_path / "curated" / "usdjpy"
    manifest = tmp_path / "data_manifest.json"
    validation_dir = tmp_path / "validation"

    backfill_cmd, refresh_cmd, paths = build_gui_data_sync_commands(
        symbol="USDJPY",
        source_dir=source_dir,
        manifest=manifest,
        validation_dir=validation_dir,
        latest_days=120,
        gap_minutes=5,
        chunk_hours=6,
        gap_exclude_weekend=True,
        run_fetch_plan=True,
        stamp="20260208T1200Z",
    )

    assert "--run-fetch-plan" in backfill_cmd
    assert "--emit-fetch-plan" in backfill_cmd
    assert "--write-latest" in refresh_cmd
    assert "--update-manifest" in refresh_cmd
    assert "--latest-days" in refresh_cmd
    assert paths["fetch_plan"].name == "usdjpy_backfill_20260208T1200Z.sh"
    assert paths["gap_report_before"].name == "usdjpy_gap_before_20260208T1200Z.json"
    assert paths["gap_report_after"].name == "usdjpy_gap_after_20260208T1200Z.json"


def test_run_gui_data_sync_executes_backfill_then_refresh(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    class _Proc:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def _fake_run(command, check, capture_output, text):  # noqa: ANN001
        assert check is True
        assert capture_output is True
        assert text is True
        calls.append(list(command))
        if "--write-latest" in command:
            return _Proc('{"symbol":"USDJPY","phase":"refresh"}')
        return _Proc('{"symbol":"USDJPY","phase":"backfill"}')

    monkeypatch.setattr("src.interfaces.cli.gui_sync.subprocess.run", _fake_run)

    result = run_gui_data_sync(
        symbol="USDJPY",
        source_dir=tmp_path / "curated" / "usdjpy",
        manifest=tmp_path / "data_manifest.json",
        validation_dir=tmp_path / "validation",
        latest_days=120,
        gap_minutes=5,
        chunk_hours=6,
        gap_exclude_weekend=True,
        run_fetch_plan=True,
    )

    assert len(calls) == 2
    assert "--run-fetch-plan" in calls[0]
    assert "--write-latest" in calls[1]
    assert result.backfill_stdout.endswith('"backfill"}')
    assert result.refresh_stdout.endswith('"refresh"}')
    assert result.warnings == []


def test_run_gui_data_sync_emits_progress_hook(monkeypatch, tmp_path: Path) -> None:
    events: list[tuple[str, dict[str, object]]] = []

    class _Proc:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def _fake_run(command, check, capture_output, text):  # noqa: ANN001
        assert check is True
        assert capture_output is True
        assert text is True
        if "--write-latest" in command:
            return _Proc('{"symbol":"USDJPY","phase":"refresh"}')
        return _Proc('{"symbol":"USDJPY","phase":"backfill"}')

    def _hook(event: str, payload: dict[str, object]) -> None:
        events.append((event, dict(payload)))

    monkeypatch.setattr("src.interfaces.cli.gui_sync.subprocess.run", _fake_run)

    run_gui_data_sync(
        symbol="USDJPY",
        source_dir=tmp_path / "curated" / "usdjpy",
        manifest=tmp_path / "data_manifest.json",
        validation_dir=tmp_path / "validation",
        latest_days=120,
        gap_minutes=5,
        chunk_hours=6,
        gap_exclude_weekend=True,
        run_fetch_plan=True,
        progress_hook=_hook,
    )

    names = [name for name, _ in events]
    assert names == [
        "sync.backfill.start",
        "sync.backfill.done",
        "sync.refresh.start",
        "sync.refresh.done",
    ]
    assert events[0][1]["progress_pct"] == 10
    assert events[-1][1]["progress_pct"] == 95


def test_run_gui_data_sync_tolerates_backfill_no_data_failure(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    class _Proc:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def _fake_run(command, check, capture_output, text):  # noqa: ANN001
        assert check is True
        assert capture_output is True
        assert text is True
        calls.append(list(command))
        if "--run-fetch-plan" in command:
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=command,
                stderr="No data fetched; nothing to write",
            )
        return _Proc('{"symbol":"USDJPY","phase":"refresh"}')

    monkeypatch.setattr("src.interfaces.cli.gui_sync.subprocess.run", _fake_run)

    result = run_gui_data_sync(
        symbol="USDJPY",
        source_dir=tmp_path / "curated" / "usdjpy",
        manifest=tmp_path / "data_manifest.json",
        validation_dir=tmp_path / "validation",
        latest_days=120,
        gap_minutes=5,
        chunk_hours=6,
        gap_exclude_weekend=True,
        run_fetch_plan=True,
    )

    assert len(calls) == 2
    assert "--run-fetch-plan" in calls[0]
    assert "--write-latest" in calls[1]
    assert "No data fetched; nothing to write" in result.backfill_stdout
    assert result.refresh_stdout.endswith('"refresh"}')
    assert result.warnings == ["no_data_fetched_during_backfill"]


def test_run_gui_data_sync_stops_before_backfill_when_requested(
    monkeypatch, tmp_path: Path
) -> None:
    def _unexpected_run(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("subprocess.run should not be called when stop is requested")

    monkeypatch.setattr("src.interfaces.cli.gui_sync.subprocess.run", _unexpected_run)

    with pytest.raises(GuiDataSyncStopped):
        run_gui_data_sync(
            symbol="USDJPY",
            source_dir=tmp_path / "curated" / "usdjpy",
            manifest=tmp_path / "data_manifest.json",
            validation_dir=tmp_path / "validation",
            latest_days=120,
            gap_minutes=5,
            chunk_hours=6,
            gap_exclude_weekend=True,
            run_fetch_plan=True,
            should_stop=lambda: True,
        )
