"""Helpers for tracking the profit readiness lever statuses."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev
from pathlib import Path
import glob
from typing import Any, Iterable, Mapping

DEFAULT_PROFIT_READINESS_PATH = Path("metrics/profit_readiness.jsonl")
ALLOWED_STATUSES = {"ok", "warning", "alert"}
EXIT_OK = 0
EXIT_WARN = 80
EXIT_GUARDED = 62
EXIT_HALT = 63
EXIT_STALE = 78


class ProfitReadinessError(RuntimeError):
    """Raised when readiness records cannot be read or written."""

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: list[dict[str, Any]] = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


@dataclass(frozen=True)
class ProfitReadinessEntry:
    lever: str
    status: str
    evidence: list[str]
    notes: str | None
    actor: str | None
    timestamp: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "lever": self.lever,
            "status": self.status,
            "evidence": list(self.evidence),
            "notes": self.notes,
            "actor": self.actor,
            "timestamp": self.timestamp,
        }


def record_readiness(
    *,
    lever: str,
    status: str,
    evidence: Iterable[str] | None = None,
    notes: str | None = None,
    actor: str | None = None,
    path: Path = DEFAULT_PROFIT_READINESS_PATH,
) -> ProfitReadinessEntry:
    """Append a readiness event to metrics/profit_readiness.jsonl."""

    if status not in ALLOWED_STATUSES:
        raise ProfitReadinessError(f"Unsupported status '{status}'. Allowed: {sorted(ALLOWED_STATUSES)}")
    payload = ProfitReadinessEntry(
        lever=lever,
        status=status,
        evidence=list(evidence or []),
        notes=notes,
        actor=actor,
        timestamp=_utcnow(),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload.to_mapping(), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return payload


def load_recent_readiness(
    *,
    path: Path = DEFAULT_PROFIT_READINESS_PATH,
    lever_filter: Iterable[str] | None = None,
    limit: int = 10,
) -> list[ProfitReadinessEntry]:
    """Return the most recent readiness entries, optionally filtered by lever."""

    entries = _read_jsonl(path)
    if lever_filter:
        allowed = {lever.lower() for lever in lever_filter}
        entries = [item for item in entries if item.get("lever", "").lower() in allowed]
    tail = entries[-limit:]
    return [
        ProfitReadinessEntry(
            lever=str(item.get("lever", "")),
            status=str(item.get("status", "ok")),
            evidence=list(item.get("evidence", [])),
            notes=item.get("notes"),
            actor=item.get("actor"),
            timestamp=str(item.get("timestamp", "")),
        )
        for item in tail
    ]


def latest_by_lever(
    *,
    path: Path = DEFAULT_PROFIT_READINESS_PATH,
    levers: Iterable[str] | None = None,
) -> dict[str, ProfitReadinessEntry]:
    """Return the most recent entry for each lever."""

    entries = _read_jsonl(path)
    levers_normalised = {lever.lower(): lever for lever in levers or []}
    latest: dict[str, ProfitReadinessEntry] = {}
    for item in entries:
        lever = str(item.get("lever", ""))
        if not lever:
            continue
        lower = lever.lower()
        if levers and lower not in levers_normalised:
            continue
        latest[lever] = ProfitReadinessEntry(
            lever=lever,
            status=str(item.get("status", "ok")),
            evidence=list(item.get("evidence", [])),
            notes=item.get("notes"),
            actor=item.get("actor"),
            timestamp=str(item.get("timestamp", "")),
        )
    return latest


# --------------------------------------------------------------------------- #
# Verification helpers

def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _latest_path(glob_pattern: str) -> Path | None:
    candidates = sorted(
        (Path(match) for match in glob.glob(glob_pattern)),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _load_scoreboard(path: Path) -> Mapping[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _load_profit_loop_entries(path: Path, *, window_days: int) -> list[Mapping[str, Any]]:
    if not path.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    entries: list[Mapping[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = _parse_timestamp(payload.get("timestamp"))
        if ts is None or ts < cutoff:
            continue
        if payload.get("mode") != "live":
            continue
        entries.append(payload)
    return entries


def _profit_factor(values: list[float]) -> float:
    positives = [v for v in values if v > 0]
    negatives = [v for v in values if v < 0]
    if not negatives:
        return float("inf")
    return sum(positives) / abs(sum(negatives) or 1e-9)


def _max_drawdown(values: list[float]) -> float:
    peak = 0.0
    trough = 0.0
    cumulative = 0.0
    dd = 0.0
    for value in values:
        cumulative += value
        if cumulative > peak:
            peak = cumulative
            trough = cumulative
        if cumulative < trough:
            trough = cumulative
            dd = min(dd, trough - peak)
    return abs(dd)


@dataclass(frozen=True)
class ProfitReadinessResult:
    status: str
    exit_code: int
    metrics: Mapping[str, float]
    sample_count: int
    evidence: list[str]
    watchlist: int
    stale: list[str]


def verify_profit_readiness(
    *,
    window_days: int = 30,
    min_samples: int = 20,
    alpha_glob: str = "scoreboard/alpha/*.json",
    bridge_glob: str = "scoreboard/bridge/*.json",
    profit_loop_path: Path = Path("metrics") / "profit_loop.jsonl",
    profit_loop_daily: Path = Path("reports") / "performance" / "profit_loop_daily.md",
    execution_bridge_path: Path = Path("metrics") / "execution_bridge.jsonl",
    live_bridge_glob: str = "reports/execution/live_bridge_*.md",
    staleness_days: int = 7,
    profit_loop_hours: int = 48,
    require_auto_execute: bool = False,
) -> ProfitReadinessResult:
    """Evaluate profit readiness KPIs and return a result with exit codes.

    Exit codes:
    - 0: all good
    - 80: KPI warning
    - 62: data insufficient (guarded)
    - 63: KPI hard fail (halt)
    - 78: evidence missing or stale
    """

    now = datetime.now(timezone.utc)
    stale: list[str] = []

    alpha_path = _latest_path(alpha_glob)
    bridge_path = _latest_path(bridge_glob)
    live_bridge_path = _latest_path(live_bridge_glob)

    required: dict[str, Path | None] = {
        "scoreboard_alpha": alpha_path,
        "scoreboard_bridge": bridge_path,
        "profit_loop_daily": profit_loop_daily if profit_loop_daily.exists() else None,
        "execution_bridge": execution_bridge_path if execution_bridge_path.exists() else None,
        "profit_loop": profit_loop_path if profit_loop_path.exists() else None,
        "live_bridge": live_bridge_path,
    }
    missing = [name for name, path in required.items() if path is None]
    if missing:
        raise ProfitReadinessError(f"Evidence missing: {', '.join(missing)}", exit_code=EXIT_STALE)

    def _is_stale(path: Path, *, max_age: timedelta) -> bool:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return now - mtime > max_age

    if _is_stale(alpha_path, max_age=timedelta(days=staleness_days)):
        stale.append(str(alpha_path))
    if _is_stale(bridge_path, max_age=timedelta(days=staleness_days)):
        stale.append(str(bridge_path))
    if _is_stale(execution_bridge_path, max_age=timedelta(days=staleness_days)):
        stale.append(str(execution_bridge_path))
    if _is_stale(profit_loop_path, max_age=timedelta(hours=profit_loop_hours)):
        stale.append(str(profit_loop_path))
    if _is_stale(profit_loop_daily, max_age=timedelta(hours=profit_loop_hours)):
        stale.append(str(profit_loop_daily))
    if live_bridge_path and _is_stale(live_bridge_path, max_age=timedelta(days=staleness_days)):
        stale.append(str(live_bridge_path))

    if stale:
        raise ProfitReadinessError(f"Evidence stale: {', '.join(stale)}", exit_code=EXIT_STALE)

    entries = _load_profit_loop_entries(profit_loop_path, window_days=window_days)
    sample_count = len(entries)
    rr_values = [float(item.get("fill_rr", 0.0)) for item in entries]
    pf = _profit_factor(rr_values) if rr_values else 0.0
    sharpe = 0.0
    if rr_values:
        mu = mean(rr_values)
        sigma = pstdev(rr_values) or 1e-6
        sharpe = mu / sigma
    max_dd = _max_drawdown(rr_values) if rr_values else 0.0

    spread_penalty = 0.0
    watchlist = 0
    for scoreboard_path in (alpha_path, bridge_path):
        payload = _load_scoreboard(scoreboard_path)
        if not payload:
            continue
        strategies = payload.get("strategies") or []
        for strategy in strategies:
            spread_penalty = max(spread_penalty, float(strategy.get("spread_penalty", 0.0)))
            reasons = strategy.get("watchlist_reasons") or []
            if reasons:
                watchlist += 1

    if sample_count < min_samples:
        raise ProfitReadinessError(
            f"Insufficient profit loop samples ({sample_count} < {min_samples})",
            exit_code=EXIT_GUARDED,
        )

    status = "ok"
    exit_code = EXIT_OK

    if (
        pf < 1.05
        or sharpe < 0.8
        or max_dd > 0.10
        or spread_penalty > 0.08
        or watchlist >= 2
    ):
        status = "alert"
        exit_code = EXIT_HALT
    elif (
        pf < 1.15
        or sharpe < 0.9
        or max_dd > 0.09
        or spread_penalty > 0.05
        or watchlist >= 1
    ):
        status = "warning"
        exit_code = EXIT_WARN

    metrics = {
        "profit_factor": pf,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "spread_penalty": spread_penalty,
    }

    if require_auto_execute:
        auto_ok = (
            pf >= 1.25
            and sharpe >= 1.05
            and max_dd <= 0.08
            and spread_penalty <= 0.05
            and watchlist == 0
        )
        if not auto_ok:
            raise ProfitReadinessError(
                "Hands-off auto_execute criteria not satisfied",
                exit_code=EXIT_GUARDED,
            )

    evidence = [str(path) for path in required.values() if path]

    return ProfitReadinessResult(
        status=status,
        exit_code=exit_code,
        metrics=metrics,
        sample_count=sample_count,
        evidence=evidence,
        watchlist=watchlist,
        stale=stale,
    )
