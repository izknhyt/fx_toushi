"""Tests for the ``tradectl preflight`` helper."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

from src.core.health import HealthMonitor
from src.interfaces.cli.preflight import preflight


def _fake_runner():
    def _run(command: list[str]) -> CompletedProcess[str]:
        if command[:2] == ["poetry", "--version"]:
            return CompletedProcess(command, 0, "Poetry (version 1.8.0)\n", "")
        if command and Path(command[0]).name == "systemsetup":
            return CompletedProcess(command, 0, "Network Time Server: time.apple.com\n", "")
        if command and Path(command[0]).name == "sntp":
            return CompletedProcess(command, 0, "offset is 0.001 sec\n", "")
        return CompletedProcess(command, 0, "", "")

    return _run


def _copy_profile(target_root: Path, profile: str) -> Path:
    target_root.mkdir(parents=True, exist_ok=True)
    src_path = Path("config/profiles") / f"{profile}.yaml"
    dst_path = target_root / f"{profile}.yaml"
    dst_path.write_text(src_path.read_text(encoding="utf-8"), encoding="utf-8")
    return dst_path


def test_preflight_succeeds_when_all_checks_pass(tmp_path: Path) -> None:
    profile_root = tmp_path / "profiles"
    _copy_profile(profile_root, "backtest")
    backup_log = tmp_path / "backup.log"
    backup_log.write_text("ok\n", encoding="utf-8")

    payload = preflight(
        profile="backtest",
        json_output=True,
        ntp_check=False,
        smtp_check=False,
        preflight_log=tmp_path / "preflight.log",
        backup_log=backup_log,
        cfg_schema_path=Path("docs/schemas/cfg.schema.json"),
        profile_root=profile_root,
        time_sync_metrics=tmp_path / "time_sync.jsonl",
        health_monitor=HealthMonitor(),
        workspace_root=tmp_path,
        command_runner=_fake_runner(),
        python_version=(3, 12, 0),
    )

    assert payload["status"] == "ok"
    assert payload["exit_code"] == 0
    assert Path(payload["logged_to"]).exists()
    assert payload["health"]["status"] == "ok"


def test_preflight_marks_degraded_on_backup_missing(tmp_path: Path) -> None:
    profile_root = tmp_path / "profiles"
    _copy_profile(profile_root, "backtest")

    payload = preflight(
        profile="backtest",
        json_output=True,
        ntp_check=False,
        smtp_check=False,
        preflight_log=tmp_path / "preflight.log",
        backup_log=tmp_path / "missing.log",
        cfg_schema_path=Path("docs/schemas/cfg.schema.json"),
        profile_root=profile_root,
        time_sync_metrics=tmp_path / "time_sync.jsonl",
        health_monitor=HealthMonitor(),
        workspace_root=tmp_path,
        command_runner=_fake_runner(),
        python_version=(3, 12, 0),
    )

    fail_ids = {item["id"] for item in payload["checks"] if item.get("status") == "fail"}
    assert "backup" in fail_ids
    assert payload["status"] == "fail"
    assert payload["exit_code"] == 1
    assert payload["health"]["status"] == "degraded"
