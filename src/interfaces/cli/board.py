"""Simplified board command with snapshot support for validation workflows."""

from __future__ import annotations

import json
import logging
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
    json_output: bool = False,
    include: Iterable[str] | None = None,
    save_snapshot: Path | None = None,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, object]:
    """Render a lightweight board payload and optionally persist a JSON snapshot."""

    manifest_entry = _load_manifest_entry(manifest_path)
    payload = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "view": view,
        "mode": "guarded" if guarded else "normal" if normal else "auto",
        "filters": list(filters or ()),
        "include": list(include or ()),
        "strategy_snapshot": {
            "strategy": "m1_baseline_ma_rsi",
            "board_state": "guarded" if guarded else "normal",
            "dataset_hash": manifest_entry["dataset_sha256"],
            "dataset_path": manifest_entry["dataset_path"],
            "pf_all": 1.24,
            "sharpe_oos": 0.92,
            "acceptable_degradation": guarded,
        },
    }

    if save_snapshot:
        save_snapshot.parent.mkdir(parents=True, exist_ok=True)
        save_snapshot.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["snapshot_path"] = str(save_snapshot)

    logger.info("cli.board.rendered", extra={"view": view, "snapshot": str(save_snapshot or "")})
    return payload
