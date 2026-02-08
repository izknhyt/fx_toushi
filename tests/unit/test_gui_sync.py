from __future__ import annotations

from pathlib import Path

from src.interfaces.cli.gui_sync import build_gui_data_sync_commands, run_gui_data_sync


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
