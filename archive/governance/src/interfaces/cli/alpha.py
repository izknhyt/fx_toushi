"""Alpha tooling commands (review, scoreboard bridge lookups, etc.)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from src.core.schema_registry import build_schema_registry
from src.strategies.alpha_pulse import AlphaPulseInputs, AlphaPulseSynthesizer

DEFAULT_BRIDGE_DIR = Path("scoreboard") / "bridge"
DEFAULT_PROFIT_LOOP_METRICS = Path("metrics") / "profit_loop.jsonl"
DEFAULT_ALPHA_PROFILE = "usd_jpy_breakout"
DEFAULT_ALPHA_PULSE_SCHEMA = Path("docs") / "schemas" / "alpha_pulse.schema.json"


class AlphaReviewError(RuntimeError):
    """Raised when alpha review cannot be completed."""

    def __init__(self, message: str, payload: Mapping[str, object] | None = None) -> None:
        super().__init__(message)
        self.payload = payload


class AlphaWatchlistAlertError(AlphaReviewError):
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


def preview(
    *,
    pair: str,
    regime: str,
    profile_id: str = DEFAULT_ALPHA_PROFILE,
    spread_cooldown: float = 0.0,
    latency_minutes: float = 0.0,
    account_equity: float = 1.0,
    entry_window_pips: tuple[float, float] = (0.0, 0.0),
    board_mode: str = "normal",
    momentum_score: float = 0.5,
    mean_reversion_score: float = 0.5,
    macro_score: float = 0.5,
    dry_run: bool = False,
    validate_schema: bool = False,
    schema_path: Path = DEFAULT_ALPHA_PULSE_SCHEMA,
) -> Mapping[str, object]:
    synthesizer = AlphaPulseSynthesizer(profile_id=profile_id)
    pulse = synthesizer.refresh(
        AlphaPulseInputs(
            pair=pair,
            regime=regime,
            momentum_score=momentum_score,
            mean_reversion_score=mean_reversion_score,
            macro_score=macro_score,
            spread_cooldown_factor=spread_cooldown,
            latency_minutes=latency_minutes,
            account_equity=account_equity,
            entry_window_pips=entry_window_pips,
            board_mode=board_mode,
        )
    )
    payload: dict[str, object] = {
        "status": "ok",
        "schema_version": "alpha.pulse.v1",
        "dry_run": dry_run,
        "profile_id": profile_id,
        "inputs": {
            "pair": pair,
            "regime": regime,
            "spread_cooldown": spread_cooldown,
            "latency_minutes": latency_minutes,
            "account_equity": account_equity,
            "entry_window_pips": list(entry_window_pips),
            "board_mode": board_mode,
            "momentum_score": momentum_score,
            "mean_reversion_score": mean_reversion_score,
            "macro_score": macro_score,
        },
        "pulse": pulse.to_dict(),
    }
    if validate_schema:
        _validate_payload(payload, schema_path=schema_path)
    return payload


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

    profit_samples = _read_profit_loop_metrics(
        profit_loop_metrics_path, strategy=strategy, limit=profit_loop_limit
    )
    payload["profit_loop_samples"] = profit_samples
    payload["week"] = resolved_week

    if scoreboard_entry:
        reasons = list(scoreboard_entry.get("watchlist_reasons") or [])
        if reasons:
            raise AlphaWatchlistAlertError(
                "Scoreboard watchlist reasons present",
                payload=payload,
            )

    return payload


def _validate_payload(payload: Mapping[str, object], *, schema_path: Path) -> None:
    schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema_data)
    registry = build_schema_registry(schema_path)
    validator = Draft202012Validator(schema_data, registry=registry)
    validator.validate(payload)


__all__ = [
    "AlphaReviewError",
    "AlphaWatchlistAlertError",
    "preview",
    "review",
]
