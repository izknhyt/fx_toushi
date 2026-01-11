"""Preflight checks for ``tradectl preflight`` (see §17.5)."""

from __future__ import annotations

import json
import logging
import os
import shutil
import smtplib
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from jsonschema import Draft202012Validator, ValidationError
from src.core.health import HealthMonitor
from src.core.time_sync import (
    DEFAULT_HEALTH_ACTION_AUDIT,
    DEFAULT_HEALTH_STATE_PATH,
    DEFAULT_HEALTH_SUGGEST_LOG,
    DEFAULT_OPS_WORKLOG,
    TimeSyncGuard,
)
from src.core.schema_registry import build_schema_registry

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_PREFLIGHT_LOG",
    "DEFAULT_BACKUP_LOG",
    "DEFAULT_CFG_SCHEMA",
    "DEFAULT_PROFILE_ROOT",
    "DEFAULT_TIME_SYNC_METRICS",
    "preflight",
]

DEFAULT_PREFLIGHT_LOG = Path("logs/ops/preflight.log")
DEFAULT_BACKUP_LOG = Path("logs/ops/backup.log")
DEFAULT_CFG_SCHEMA = Path("docs/schemas/cfg.schema.json")
DEFAULT_PROFILE_ROOT = Path("config/profiles")
DEFAULT_TIME_SYNC_METRICS = Path("metrics/time_sync.jsonl")
_MIN_PYTHON = (3, 12)
_SMTP_HOST_ENV = "SMTP_HOST"
_SMTP_PORT_ENV = "SMTP_PORT"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _run_command(
    command: Sequence[str],
    runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] | None = None,
) -> subprocess.CompletedProcess[str]:
    runner = runner or (
        lambda args: subprocess.run(args, capture_output=True, text=True, check=False)
    )
    return runner(command)


def _check_python_poetry(
    *,
    python_version: tuple[int, int, int] | None = None,
    runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, object]:
    version_info = python_version or sys.version_info[:3]
    status = "ok"
    detail: list[str] = []
    if version_info < _MIN_PYTHON:
        status = "fail"
        expected = ".".join(map(str, _MIN_PYTHON))
        found = ".".join(map(str, version_info))
        detail.append(f"python_version_expected>={expected},found={found}")
    poetry = _run_command(["poetry", "--version"], runner=runner)
    poetry_version = poetry.stdout.strip() or poetry.stderr.strip()
    if poetry.returncode != 0:
        status = "fail"
        detail.append("poetry_not_available")
    return {
        "id": "python_poetry",
        "status": status,
        "python_version": ".".join(map(str, version_info)),
        "poetry_version": poetry_version or "unknown",
        "detail": ";".join(detail) if detail else None,
    }


def _check_disk_and_permissions(
    *, workspace_root: Path, preflight_log: Path, threshold_gb: float = 5.0
) -> dict[str, object]:
    usage = shutil.disk_usage(workspace_root)
    free_gb = usage.free / (1024**3)
    status = "ok" if free_gb >= threshold_gb else "fail"
    detail = f"free_gb={free_gb:.2f},threshold_gb={threshold_gb:.2f}"
    write_ok = True
    test_path = preflight_log.parent / ".preflight_write_test"
    try:
        preflight_log.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text("ok", encoding="utf-8")
        test_path.unlink(missing_ok=True)
    except OSError as exc:
        write_ok = False
        status = "fail"
        detail = f"{detail};write_error={exc}"
    return {
        "id": "disk",
        "status": status,
        "free_gb": round(free_gb, 2),
        "write_ok": write_ok,
        "detail": detail,
    }


def _check_ntp(
    *,
    enabled: bool,
    runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] | None,
    metrics_path: Path,
    preferred_server: str | None = None,
) -> dict[str, object]:
    if not enabled:
        return {"id": "ntp", "status": "skipped", "detail": "ntp_check_disabled"}

    server = preferred_server
    server_detail = None
    # macOS specific helper; ignore failures (treated as WARN)
    systemsetup = shutil.which("systemsetup")
    if not server and systemsetup:
        result = _run_command([systemsetup, "-getnetworktimeserver"], runner=runner)
        if result.returncode == 0 and result.stdout:
            parts = result.stdout.strip().split(":")
            if parts:
                server = parts[-1].strip() or None
        else:
            server_detail = result.stderr.strip() or "systemsetup_unavailable"

    status = "warn"
    drift_ms: float | None = None
    if server:
        sntp_bin = shutil.which("sntp") or "/usr/sbin/sntp"
        if Path(sntp_bin).exists():
            result = _run_command([sntp_bin, server], runner=runner)
            if result.returncode == 0:
                status = "ok"
                drift_ms = _parse_sntp_offset_ms(result.stdout)
            else:
                server_detail = result.stderr.strip() or "sntp_failed"
        else:
            server_detail = "sntp_not_found"
    else:
        server_detail = server_detail or "ntp_server_missing"

    metrics_entry = {
        "ts": _utcnow_iso(),
        "server": server,
        "clock_drift_ms": drift_ms,
        "status": status,
    }
    _append_jsonl(metrics_path, metrics_entry)

    return {
        "id": "ntp",
        "status": status,
        "server": server,
        "clock_drift_ms": drift_ms,
        "detail": server_detail,
    }


def _parse_sntp_offset_ms(output: str) -> float | None:
    for line in output.splitlines():
        if "offset" in line and "sec" in line:
            try:
                part = line.split("offset", 1)[1]
                value_str = part.split()[0]
                return float(value_str) * 1000.0
            except (IndexError, ValueError):
                continue
    return None


def _check_smtp(
    *, enabled: bool, host: str | None, port: int, timeout: float = 5.0
) -> dict[str, object]:
    if not enabled:
        return {"id": "smtp", "status": "skipped", "detail": "smtp_check_disabled"}
    status = "fail"
    detail = None
    try:
        with smtplib.SMTP(host=host or "localhost", port=port, timeout=timeout) as client:
            code, _ = client.noop()
            if 200 <= code < 300:
                status = "ok"
            else:
                detail = f"noop_failed_code={code}"
    except Exception as exc:  # pragma: no cover - network variability
        detail = str(exc)
    return {
        "id": "smtp",
        "status": status,
        "host": host or "localhost",
        "port": port,
        "detail": detail,
    }


def _build_validator(schema_path: Path) -> Draft202012Validator:
    schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema_data)
    registry = build_schema_registry(schema_path)
    return Draft202012Validator(schema_data, registry=registry)


def _check_profile_schema(
    *, profile: str, profile_root: Path, schema_path: Path
) -> dict[str, object]:
    profile_path = profile_root / f"{profile}.yaml"
    if not profile_path.exists():
        return {
            "id": "config_profile",
            "status": "fail",
            "detail": f"missing_profile:{profile_path}",
        }
    try:
        validator = _build_validator(schema_path)
        payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        validator.validate(payload)
        return {"id": "config_profile", "status": "ok", "profile_path": str(profile_path)}
    except ValidationError as exc:
        return {
            "id": "config_profile",
            "status": "fail",
            "profile_path": str(profile_path),
            "detail": exc.message,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "id": "config_profile",
            "status": "fail",
            "profile_path": str(profile_path),
            "detail": str(exc),
        }


def _check_backup_log(*, backup_log: Path, warn_after_days: int = 7) -> dict[str, object]:
    if not backup_log.exists():
        return {"id": "backup", "status": "fail", "detail": f"missing_backup_log:{backup_log}"}
    mtime = datetime.fromtimestamp(backup_log.stat().st_mtime, tz=timezone.utc)
    age_days = (datetime.now(timezone.utc) - mtime) / timedelta(days=1)
    status = "ok" if age_days <= warn_after_days else "warn"
    detail = f"age_days={age_days:.1f}"
    return {"id": "backup", "status": status, "age_days": round(age_days, 2), "detail": detail}


def preflight(
    profile: str,
    *,
    json_output: bool = False,
    ntp_check: bool = True,
    smtp_check: bool = False,
    preflight_log: Path = DEFAULT_PREFLIGHT_LOG,
    backup_log: Path = DEFAULT_BACKUP_LOG,
    cfg_schema_path: Path = DEFAULT_CFG_SCHEMA,
    profile_root: Path = DEFAULT_PROFILE_ROOT,
    time_sync_metrics: Path = DEFAULT_TIME_SYNC_METRICS,
    health_monitor: HealthMonitor | None = None,
    health_state_path: Path = DEFAULT_HEALTH_STATE_PATH,
    workspace_root: Path | None = None,
    command_runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] | None = None,
    python_version: tuple[int, int, int] | None = None,
) -> dict[str, object]:
    """Execute the preflight checklist."""

    monitor = health_monitor or HealthMonitor()
    now = _utcnow_iso()
    workspace = workspace_root or Path(".")

    results: list[dict[str, object]] = []
    results.append(_check_python_poetry(python_version=python_version, runner=command_runner))
    results.append(
        _check_disk_and_permissions(workspace_root=workspace, preflight_log=preflight_log)
    )
    results.append(
        _check_ntp(
            enabled=ntp_check,
            runner=command_runner,
            metrics_path=time_sync_metrics,
            preferred_server=os.getenv("NTP_SERVER"),
        )
    )
    time_sync = TimeSyncGuard().evaluate(
        metrics_path=time_sync_metrics,
        monitor=monitor,
        health_state_path=health_state_path,
        suggest_log_path=DEFAULT_HEALTH_SUGGEST_LOG,
        audit_path=DEFAULT_HEALTH_ACTION_AUDIT,
        ops_worklog_path=DEFAULT_OPS_WORKLOG,
        persist_health_state=True,
        log_events=True,
    )
    smtp_host = os.getenv(_SMTP_HOST_ENV)
    smtp_port = int(os.getenv(_SMTP_PORT_ENV, "25"))
    results.append(_check_smtp(enabled=smtp_check, host=smtp_host, port=smtp_port))
    results.append(
        _check_profile_schema(
            profile=profile, profile_root=profile_root, schema_path=cfg_schema_path
        )
    )
    results.append(_check_backup_log(backup_log=backup_log))

    has_failures = any(item.get("status") == "fail" for item in results)
    has_warn = any(item.get("status") == "warn" for item in results)
    status = "fail" if has_failures else "warn" if has_warn else "ok"
    exit_code = 1 if has_failures else 0

    if has_failures:
        failed_ids = [item["id"] for item in results if item.get("status") == "fail"]
        monitor.raise_condition(
            "degraded",
            "preflight",
            detail=f"failed_checks={','.join(str(fid) for fid in failed_ids)}",
            recommended_action="See logs/ops/preflight.log",
        )

    payload = {
        "timestamp": now,
        "profile": profile,
        "status": status,
        "checks": results,
        "time_sync": time_sync.to_dict(),
        "exit_code": exit_code,
        "logged_to": str(preflight_log),
        "health": monitor.to_dict(),
    }

    log_entry = {
        "ts": now,
        "profile": profile,
        "status": status,
        "checks": results,
        "exit_code": exit_code,
    }
    _append_jsonl(preflight_log, log_entry)
    logger.info("cli.preflight.completed", extra={"status": status, "failures": has_failures})

    return payload
