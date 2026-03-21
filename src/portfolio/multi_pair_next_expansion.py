"""Execution ledger bridge for the next pair expansion after steady-state qualification."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

DEFAULT_MULTI_PAIR_NEXT_EXPANSION_LEDGER = Path(
    "logs/ops/multi_pair_next_expansion_execution.jsonl"
)


def append_multi_pair_next_expansion_execution(
    record: Mapping[str, Any],
    *,
    ledger_path: Path = DEFAULT_MULTI_PAIR_NEXT_EXPANSION_LEDGER,
) -> dict[str, Any]:
    payload = {
        "event": "multi_pair.next_expansion.execution",
        "ts": str(record.get("ts") or _utcnow_iso()),
        **{key: value for key, value in record.items() if key != "event"},
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")
    return payload


def load_multi_pair_next_expansion_execution_history(
    ledger_path: Path = DEFAULT_MULTI_PAIR_NEXT_EXPANSION_LEDGER,
) -> list[dict[str, Any]]:
    if not ledger_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping) and str(payload.get("event") or "") == "multi_pair.next_expansion.execution":
            rows.append(dict(payload))
    rows.sort(key=lambda item: str(item.get("ts") or ""))
    return rows


def build_multi_pair_next_expansion_execution_summary(
    ops_summary: Mapping[str, Any],
    *,
    ledger_path: Path = DEFAULT_MULTI_PAIR_NEXT_EXPANSION_LEDGER,
) -> dict[str, Any]:
    steady_state_status = str(ops_summary.get("multi_pair_steady_state_status") or "unknown")
    ledger_rows_all = load_multi_pair_next_expansion_execution_history(ledger_path)
    latest_any = dict(ledger_rows_all[-1]) if ledger_rows_all else {}
    current_symbol = str(
        ops_summary.get("multi_pair_expansion_next_symbol")
        or latest_any.get("current_symbol")
        or ((ops_summary.get("multi_pair_steady_state_summary") or {}).get("expanded_symbol") or "")
    )
    next_symbol = str(ops_summary.get("multi_pair_steady_state_next_symbol") or latest_any.get("next_symbol") or "")
    runner_command = str(ops_summary.get("multi_pair_steady_state_runner_command") or "")
    execute_command = f"{runner_command} --run" if runner_command else ""
    ledger_rows = [
        row
        for row in ledger_rows_all
        if str(row.get("current_symbol") or "") == current_symbol
        and str(row.get("next_symbol") or "") == next_symbol
    ]
    latest = dict(ledger_rows[-1]) if ledger_rows else {}

    if not latest and steady_state_status != "ready_for_next_pair_review":
        return {
            "status": "blocked",
            "execution_status": "blocked",
            "current_symbol": current_symbol,
            "next_symbol": next_symbol,
            "runner_command": runner_command,
            "execute_command": execute_command,
            "recommended_action": "maintain_pair_expansion_rollout",
            "blockers": [f"multi_pair_steady_state_status={steady_state_status}"],
            "clear_conditions": ["multi_pair_steady_state_status=ready_for_next_pair_review"],
            "latest": latest,
            "recent": ledger_rows[-5:],
            "ledger_path": str(ledger_path),
        }

    latest_status = str(latest.get("status") or "missing")
    if latest_status in {"missing", ""}:
        return {
            "status": "ready_to_start",
            "execution_status": "missing",
            "current_symbol": current_symbol,
            "next_symbol": next_symbol,
            "runner_command": runner_command,
            "execute_command": execute_command,
            "recommended_action": "start_next_pair_expansion_rollout",
            "blockers": [],
            "clear_conditions": [],
            "latest": {},
            "recent": [],
            "ledger_path": str(ledger_path),
        }
    if latest_status in {"started", "running"}:
        return {
            "status": "monitoring",
            "execution_status": latest_status,
            "current_symbol": current_symbol,
            "next_symbol": next_symbol,
            "runner_command": runner_command,
            "execute_command": execute_command,
            "recommended_action": "monitor_next_pair_expansion_rollout",
            "blockers": [],
            "clear_conditions": [],
            "latest": latest,
            "recent": ledger_rows[-5:],
            "ledger_path": str(ledger_path),
        }
    if latest_status == "completed":
        return {
            "status": "handoff_to_rollout_guardrail",
            "execution_status": latest_status,
            "current_symbol": current_symbol,
            "next_symbol": next_symbol,
            "runner_command": runner_command,
            "execute_command": execute_command,
            "recommended_action": "review_next_pair_expansion_rollout_evidence",
            "blockers": [],
            "clear_conditions": [],
            "latest": latest,
            "recent": ledger_rows[-5:],
            "ledger_path": str(ledger_path),
        }
    return {
        "status": "re_review_required",
        "execution_status": latest_status,
        "current_symbol": current_symbol,
        "next_symbol": next_symbol,
        "runner_command": runner_command,
        "execute_command": execute_command,
        "recommended_action": "re_review_next_pair_expansion_rollout",
        "blockers": [f"next_pair_expansion_execution_status={latest_status}"],
        "clear_conditions": ["rerun_next_pair_expansion_rollout"],
        "latest": latest,
        "recent": ledger_rows[-5:],
        "ledger_path": str(ledger_path),
    }


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "DEFAULT_MULTI_PAIR_NEXT_EXPANSION_LEDGER",
    "append_multi_pair_next_expansion_execution",
    "build_multi_pair_next_expansion_execution_summary",
    "load_multi_pair_next_expansion_execution_history",
]
