"""Persist gate_state.json with cfg/data hashes resolved from env or manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.core.gate import GateAggregator, GateState


def _load_state(path: Path) -> GateState:
    return GateState.load(path) if path.exists() else GateState()


def persist_gate_state(
    path: Path, *, cfg_hash: str | None, data_hash: str | None
) -> dict[str, object]:
    state = _load_state(path)
    agg = GateAggregator(initial_state=state)
    persisted = agg.persist_latest(path=path, cfg_hash=cfg_hash, data_hash=data_hash)
    snap = agg.snapshot()
    return {
        "status": "ok",
        "path": str(persisted),
        "cfg_hash": snap.cfg_hash,
        "data_hash": snap.data_hash,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist GateState with cfg/data hashes")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("snapshots/latest/gate_state.json"),
        help="Output gate_state.json path",
    )
    parser.add_argument(
        "--cfg-hash",
        dest="cfg_hash",
        type=str,
        default=None,
        help="Config hash override (sha256:...)",
    )
    parser.add_argument(
        "--data-hash",
        dest="data_hash",
        type=str,
        default=None,
        help="Data hash override (sha256:...)",
    )
    args = parser.parse_args()

    payload = persist_gate_state(path=args.path, cfg_hash=args.cfg_hash, data_hash=args.data_hash)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
