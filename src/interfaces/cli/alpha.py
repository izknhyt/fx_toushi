"""Alpha tooling commands (review, scoreboard bridge lookups, etc.)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

DEFAULT_BRIDGE_DIR = Path("scoreboard") / "bridge"
DEFAULT_PROFIT_LOOP_METRICS = Path("metrics") / "profit_loop.jsonl"


class AlphaReviewError(RuntimeError):
    """Raised when alpha review cannot be completed."""

    def __init__(self, message: str, payload: Mapping[str, object] | None = None) -> None:
        super().__init__(message)
        self.payload = payload


class AlphaWatchlistAlert(AlphaReviewError):
    """Raised when the review finds watchlist reasons and should warn the caller."""


def _read_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AlphaReviewError(f"Bridge file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AlphaReviewError(f"Bridge file is malformed: {path}") from exc


def _find_bridge_file(bridge_dir: Path, week: str | None) -> Path:
    bridge_dir.mkdir(parents=True, exist_ok=True)
    if week:
        candidate = bridge_dir / f"{week}.json"
        if not candidate.exists():
            raise AlphaReviewError(f"Bridge snapshot for week '{week}' not found: {candidate}")
        return candidate
    candidates = sorted(bridge_dir.glob("*.json"))
    if not candidates:
        raise AlphaReviewError(f"No bridge snapshots found under {bridge_dir}")
    return candidates[-1]


def _load_bridge_entry(snapshot: dict[str, object], strategy: str) -> Mapping[str, object]:
    entries = snapshot.get("strategies") or []
    available: list[str] = []
    for raw in entries:
        if isinstance(raw, dict):
            entry_id = raw.get("id")
            if isinstance(entry_id, str):
                available.append(entry_id)
            if entry_id == strategy:
                return raw
    raise AlphaReviewError(
        f"Strategy '{strategy}' not present in bridge snapshot",
        payload={
            "strategy": strategy,
            "available_strategies": available,
            "bridge_week": snapshot.get("week"),
        },
    )


def _read_profit_loop_metrics(path: Path, strategy: str, limit: int) -> list[dict[str, object]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: list[dict[str, object]] = []
    for line in reversed(lines):
        if len(entries) >= limit:
            break
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("strategy_id") == strategy:
            entries.append(payload)
    return list(reversed(entries))


def review(
    *,
    strategy: str,
    week: str | None = None,
    with_scoreboard: bool = True,
    bridge_dir: Path = DEFAULT_BRIDGE_DIR,
    profit_loop_metrics_path: Path = DEFAULT_PROFIT_LOOP_METRICS,
    profit_loop_limit: int = 10,
) -> Mapping[str, object]:
    """Return alpha review payload (optionally enriched with scoreboard bridge data)."""

    payload: dict[str, object] = {
        "strategy": strategy,
        "requested_week": week,
        "scoreboard": None,
        "profit_loop_samples": [],
        "bridge_path": None,
    }

    scoreboard_entry: Mapping[str, object] | None = None
    resolved_week = week

    if with_scoreboard:
        bridge_path = _find_bridge_file(bridge_dir, week)
        snapshot = _read_json(bridge_path)
        resolved_week = snapshot.get("week") or resolved_week
        entry = _load_bridge_entry(snapshot, strategy=strategy)
        scoreboard_entry = entry
        payload["scoreboard"] = entry
        payload["bridge_path"] = str(bridge_path)
        payload["bridge_meta"] = snapshot.get("meta")

    profit_samples = _read_profit_loop_metrics(profit_loop_metrics_path, strategy=strategy, limit=profit_loop_limit)
    payload["profit_loop_samples"] = profit_samples
    payload["week"] = resolved_week

    if scoreboard_entry:
        reasons = list(scoreboard_entry.get("watchlist_reasons") or [])
        if reasons:
            raise AlphaWatchlistAlert(
                "Scoreboard watchlist reasons present",
                payload=payload,
            )

    return payload
