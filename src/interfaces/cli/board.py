"""Simplified board command with snapshot support for validation workflows."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)

DEFAULT_MANIFEST = Path("reports/data_manifest.json")

__all__ = ["board", "_load_manifest_entry"]


def _load_manifest_entry(manifest_path: Path, strategy: str = "m1_baseline_ma_rsi") -> dict[str, str]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    strategies = manifest.get("strategies") or {}
    if strategy not in strategies:
        raise KeyError(f"Strategy '{strategy}' missing in {manifest_path}")
    entry = strategies[strategy]
    if "dataset_path" not in entry:
        raise ValueError(f"Strategy '{strategy}' manifest entry missing dataset_path")
    if "dataset_sha256" not in entry:
        raise ValueError(f"Strategy '{strategy}' manifest entry missing dataset_sha256")
    return entry


def board(
    filters: Sequence[str] | None = None,
    *,
    view: str = "tickets",
    guarded: bool = False,
    normal: bool = False,
    kill_switch_state: str | None = None,
    spread_status: str | None = None,
    reduce_only: bool = False,
    json_output: bool = False,
    include: Iterable[str] | None = None,
    save_snapshot: Path | None = None,
    manifest_path: Path = DEFAULT_MANIFEST,
    profit_readiness_status: str = "ok",
    latency_data_status: str = "ok",
    slippage_data_status: str = "ok",
    kill_switch_reason: str | None = None,
    risk_disclosure_status: str = "signed",
    compat_mode: str | None = None,
) -> dict[str, object]:
    """Render a lightweight board payload and optionally persist a JSON snapshot."""

    compat_mode = compat_mode or _read_compat_env()
    manifest_entry = _load_manifest_entry(manifest_path)
    effective_kill_switch = kill_switch_state or ("guarded" if guarded else "none")
    payload = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "view": view,
        "mode": "guarded" if guarded else "normal" if normal else "auto",
        "filters": list(filters or ()),
        "include": list(include or ()),
        "auto_execute": bool(normal and not guarded and not reduce_only),
        "compat_mode": compat_mode,
        "banner": _build_banner(
            kill_switch_state=effective_kill_switch,
            spread_status=spread_status or "normal",
            reduce_only=reduce_only,
            kill_switch_reason=kill_switch_reason,
            risk_disclosure_status=risk_disclosure_status,
            compat_mode=compat_mode,
        ),
        "strategy_snapshot": {
            "strategy": "m1_baseline_ma_rsi",
            "board_state": "guarded" if guarded else "normal",
            "dataset_hash": manifest_entry["dataset_sha256"],
            "dataset_path": manifest_entry["dataset_path"],
            "pf_all": 1.24,
            "sharpe_oos": 0.92,
            "acceptable_degradation": guarded,
        },
        "badges": {
            "profit_readiness": profit_readiness_status,
            "execution_stats": {
                "latency_data_status": latency_data_status,
                "slippage_data_status": slippage_data_status,
            },
        },
        "guardrails": {
            "kill_switch_state": effective_kill_switch,
            "kill_switch_reason": kill_switch_reason,
            "spread_status": spread_status or "normal",
            "reduce_only": reduce_only,
            "risk_disclosure": risk_disclosure_status,
        },
    }

    if save_snapshot:
        save_snapshot.parent.mkdir(parents=True, exist_ok=True)
        save_snapshot.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["snapshot_path"] = str(save_snapshot)

    logger.info("cli.board.rendered", extra={"view": view, "snapshot": str(save_snapshot or "")})
    return payload


def _build_banner(
    *,
    kill_switch_state: str,
    spread_status: str,
    reduce_only: bool,
    kill_switch_reason: str | None,
    risk_disclosure_status: str,
    compat_mode: str | None,
) -> dict[str, object]:
    """Construct a minimal banner payload consistent with guardrail status."""

    banner: dict[str, object] = {"kind": "normal", "message": "Board mode normal"}

    if kill_switch_state in {"hard_stop", "soft_stop"}:
        banner["kind"] = "kill_switch"
        banner["severity"] = "hard" if kill_switch_state == "hard_stop" else "soft"
        banner["message"] = f"Kill Switch {kill_switch_state.upper()}"
        banner["runbook"] = "docs/runbooks/RUN-RISK-01.md"
        if kill_switch_reason:
            banner["reason"] = kill_switch_reason
    elif spread_status in {"block", "cooldown"}:
        banner["kind"] = "spread_guard"
        banner["severity"] = "critical" if spread_status == "block" else "warn"
        banner["message"] = f"Spread {spread_status}"
        banner["runbook"] = "docs/runbooks/RUN-SPREAD-03.md"
    elif reduce_only:
        banner["kind"] = "acceptable_degradation"
        banner["severity"] = "warn"
        banner["message"] = "Reduce-Only enforced"
        banner["runbook"] = "docs/runbooks/RUN-DATA-05.md"
    elif risk_disclosure_status.lower() == "pending" and compat_mode != "v1":
        banner["kind"] = "risk_disclosure"
        banner["severity"] = "warn"
        banner["message"] = "RiskDisclosure pending"
        banner["runbook"] = "docs/runbooks/RUN-HITL-01.md"

    return banner


def _read_compat_env() -> str | None:
    compat = os.getenv("TRADECTL_COMPAT")
    if compat:
        value = compat.strip()
        return value or None
    return None
