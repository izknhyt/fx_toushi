"""Shared GUI/shadow helpers for running and summarizing v2 completion checks."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "analysis" / "shadow"
DEFAULT_EXECUTION_LEDGER = PROJECT_ROOT / "logs" / "ops" / "v2_completion_check_execution.jsonl"
DEFAULT_RUNNER_SCRIPT = PROJECT_ROOT / "tools" / "scripts" / "run_v2_completion_check.py"


def summarize_v2_completion_check_execution(
    ledger_path: Path = DEFAULT_EXECUTION_LEDGER,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    if not ledger_path.exists():
        return {
            "status": "ok",
            "count": 0,
            "summary": {},
            "completion_summary": {},
            "latest": {},
            "recent": [],
            "ledger_path": str(ledger_path),
        }

    rows: list[dict[str, Any]] = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping) and str(payload.get("event") or "") == "v2.completion_check.execution":
            rows.append(dict(payload))

    rows.sort(key=lambda item: str(item.get("ts") or ""))
    recent = rows[-limit:] if limit > 0 else rows
    latest = dict(rows[-1]) if rows else {}

    summary: dict[str, int] = {}
    completion_summary: dict[str, int] = {}
    for row in rows:
        execution_status = str(row.get("status") or "unknown")
        summary[execution_status] = summary.get(execution_status, 0) + 1
        completion_status = str(row.get("completion_status") or "unknown")
        completion_summary[completion_status] = completion_summary.get(completion_status, 0) + 1

    return {
        "status": "ok",
        "count": len(rows),
        "summary": summary,
        "completion_summary": completion_summary,
        "latest": latest,
        "recent": recent[-5:],
        "ledger_path": str(ledger_path),
    }


def run_v2_completion_check(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    limit: int = 200,
    window_hours: int = 24,
    requested_via: str = "gui",
    ledger_path: Path = DEFAULT_EXECUTION_LEDGER,
    runner_script: Path = DEFAULT_RUNNER_SCRIPT,
    python_executable: str | None = None,
) -> dict[str, Any]:
    command = [
        _resolve_python_executable(python_executable),
        str(runner_script),
        "--output-dir",
        str(output_dir),
        "--limit",
        str(int(limit)),
        "--window-hours",
        str(int(window_hours)),
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    payload: dict[str, Any]
    if completed.returncode != 0:
        payload = {
            "status": "error",
            "completion_status": "unknown",
            "completion_candidate": False,
            "blockers": ["completion_check_failed"],
            "error": (completed.stderr or completed.stdout or "").strip() or "completion_check_failed",
        }
    else:
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {
                "status": "error",
                "completion_status": "unknown",
                "completion_candidate": False,
                "blockers": ["completion_check_invalid_output"],
                "error": completed.stdout.strip() or "completion_check_invalid_output",
            }

    record = {
        "event": "v2.completion_check.execution",
        "ts": _utcnow_iso(),
        "requested_via": requested_via,
        "runner_script": str(runner_script),
        "command": command,
        "output_dir": str(output_dir),
        "limit": int(limit),
        "window_hours": int(window_hours),
        "status": str(payload.get("status") or "unknown"),
        "completion_status": str(payload.get("completion_status") or "unknown"),
        "completion_candidate": bool(payload.get("completion_candidate")),
        "completion_recommended_action": str(payload.get("completion_recommended_action") or ""),
        "blockers": [str(item) for item in (payload.get("blockers") or [])],
        "ops_summary_json": str(payload.get("ops_summary_json") or ""),
        "completion_json": str(payload.get("completion_json") or ""),
        "error": str(payload.get("error") or ""),
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False))
        handle.write("\n")

    return {
        **payload,
        "requested_via": requested_via,
        "ledger_path": str(ledger_path),
    }


def _resolve_python_executable(python_executable: str | None) -> str:
    if python_executable:
        return python_executable
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "DEFAULT_EXECUTION_LEDGER",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_RUNNER_SCRIPT",
    "run_v2_completion_check",
    "summarize_v2_completion_check_execution",
]
