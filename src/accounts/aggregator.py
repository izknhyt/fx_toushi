"""Account aggregation and alerting utilities."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

DEFAULT_PROFILE_DIR = Path("config") / "accounts"
DEFAULT_SNAPSHOT_DIR = Path("reports") / "accounts"
DEFAULT_METRICS_PATH = Path("metrics") / "accounts_aggregator.jsonl"


@dataclass(slots=True)
class AccountProfile:
    broker_id: str
    account_id: str
    mode: str
    base_currency: str
    leverage: float
    status: str
    data_source: str | None = None
    update_interval: int | None = None
    notes: str | None = None


@dataclass(slots=True)
class PositionRecord:
    symbol: str
    side: str
    lots: float
    avg_price: float
    unrealized_pnl: float | None = None
    open_ts: str | None = None
    tags: list[str] | None = None


@dataclass(slots=True)
class AccountSnapshot:
    account_id: str
    ts: str
    balance: float
    equity: float
    margin_used: float
    free_margin: float
    open_positions: int
    floating_pnl: float | None = None
    swap: float | None = None
    status: str = "ok"
    positions: list[PositionRecord] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "ts": self.ts,
            "balance": self.balance,
            "equity": self.equity,
            "margin_used": self.margin_used,
            "free_margin": self.free_margin,
            "open_positions": self.open_positions,
            "floating_pnl": self.floating_pnl,
            "swap": self.swap,
            "status": self.status,
            "positions": [pos.__dict__ for pos in self.positions or []],
        }


@dataclass(slots=True)
class AccountAlert:
    account_id: str
    severity: str
    reason: str
    metric: str
    value: float | None
    threshold: float | None
    ts: str
    runbook_ref: str = "RUN-ACC-01"

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "severity": self.severity,
            "reason": self.reason,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
            "ts": self.ts,
            "runbook_ref": self.runbook_ref,
        }


@dataclass(slots=True)
class AggregatedState:
    ts: str
    total_equity: float
    total_margin: float
    r_eff_total: float
    account_breakdown: list[Mapping[str, Any]]
    alerts: list[AccountAlert]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "total_equity": self.total_equity,
            "total_margin": self.total_margin,
            "r_eff_total": self.r_eff_total,
            "account_breakdown": list(self.account_breakdown),
            "alerts": [alert.to_dict() for alert in self.alerts],
        }


class AccountAggregator:
    def __init__(
        self,
        *,
        profile_dir: Path = DEFAULT_PROFILE_DIR,
        snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
        metrics_path: Path = DEFAULT_METRICS_PATH,
    ) -> None:
        self._profile_dir = profile_dir
        self._snapshot_dir = snapshot_dir
        self._metrics_path = metrics_path

    def load_profiles(self) -> list[AccountProfile]:
        if not self._profile_dir.exists():
            return []
        profiles: list[AccountProfile] = []
        for path in sorted(self._profile_dir.glob("*.yaml")):
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(payload, Mapping):
                continue
            try:
                profiles.append(_profile_from_payload(payload, fallback_id=path.stem))
            except ValueError:
                continue
        return profiles

    def resolve_profile(self, profile_id: str) -> AccountProfile:
        for profile in self.load_profiles():
            if profile.account_id == profile_id:
                return profile
            if profile.broker_id == profile_id:
                return profile
            if profile_id == _slugify(profile.account_id):
                return profile
        raise ValueError(f"Unknown account profile: {profile_id}")

    def ingest_snapshot(
        self,
        *,
        profile_id: str,
        source_path: Path,
        fmt: str = "json",
        tz: str | None = None,
        append: bool = False,
    ) -> AccountSnapshot:
        profile = self.resolve_profile(profile_id)
        started = datetime.now(timezone.utc)
        snapshot = _load_snapshot(
            source_path,
            account_id=profile.account_id,
            fmt=fmt,
            tz=tz,
        )
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        target = self._snapshot_dir / f"{profile.account_id}_latest.json"
        target.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        if append:
            history = self._snapshot_dir / f"{profile.account_id}_history.jsonl"
            with history.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(snapshot.to_dict(), ensure_ascii=False))
                handle.write("\n")
        duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        self._append_metrics(
            {
                "event": "accounts.snapshot.updated",
                "account_id": profile.account_id,
                "ingest_latency_ms": duration_ms,
                "source": str(source_path),
            }
        )
        return snapshot

    def latest_snapshots(self) -> list[AccountSnapshot]:
        if not self._snapshot_dir.exists():
            return []
        snapshots: list[AccountSnapshot] = []
        for path in sorted(self._snapshot_dir.glob("*_latest.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            snapshots.append(_snapshot_from_payload(payload))
        return snapshots

    def aggregate(
        self, *, account_filter: Iterable[str] | None = None
    ) -> AggregatedState:
        snapshots = self.latest_snapshots()
        if account_filter:
            allowed = {str(item) for item in account_filter}
            snapshots = [snap for snap in snapshots if snap.account_id in allowed]
        alerts = self.generate_alerts(snapshots)
        total_equity = sum(snap.equity for snap in snapshots)
        total_margin = sum(snap.margin_used for snap in snapshots)
        r_eff_total = total_margin / total_equity if total_equity else 0.0
        breakdown = [_snapshot_summary(snap) for snap in snapshots]
        state = AggregatedState(
            ts=_utcnow_iso(),
            total_equity=round(total_equity, 2),
            total_margin=round(total_margin, 2),
            r_eff_total=round(r_eff_total, 4),
            account_breakdown=breakdown,
            alerts=alerts,
        )
        self._append_metrics(
            {
                "event": "accounts.aggregate.updated",
                "total_equity": state.total_equity,
                "total_margin": state.total_margin,
                "r_eff_total": state.r_eff_total,
                "alerts_count": len(alerts),
            }
        )
        return state

    def generate_alerts(self, snapshots: Iterable[AccountSnapshot]) -> list[AccountAlert]:
        alerts: list[AccountAlert] = []
        now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(hours=24)
        for snap in snapshots:
            ts = _parse_ts(snap.ts)
            if ts and ts < stale_cutoff:
                alerts.append(
                    AccountAlert(
                        account_id=snap.account_id,
                        severity="warn",
                        reason="data_staleness",
                        metric="snapshot_age_hours",
                        value=round((now - ts).total_seconds() / 3600.0, 2),
                        threshold=24.0,
                        ts=_utcnow_iso(),
                    )
                )
            free_margin_pct = (snap.free_margin / snap.equity * 100.0) if snap.equity else 0.0
            if free_margin_pct < 20.0:
                alerts.append(
                    AccountAlert(
                        account_id=snap.account_id,
                        severity="critical",
                        reason="free_margin_low",
                        metric="free_margin_pct",
                        value=round(free_margin_pct, 2),
                        threshold=20.0,
                        ts=_utcnow_iso(),
                    )
                )
            drawdown_pct = ((snap.balance - snap.equity) / snap.balance * 100.0) if snap.balance else 0.0
            if drawdown_pct > 10.0:
                alerts.append(
                    AccountAlert(
                        account_id=snap.account_id,
                        severity="warn",
                        reason="drawdown_high",
                        metric="drawdown_pct",
                        value=round(drawdown_pct, 2),
                        threshold=10.0,
                        ts=_utcnow_iso(),
                    )
                )
        if alerts:
            self._append_metrics(
                {
                    "event": "accounts.alert.raised",
                    "alerts_count": len(alerts),
                    "severity": sorted({alert.severity for alert in alerts}),
                }
            )
        return alerts

    def _append_metrics(self, payload: Mapping[str, Any]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": _utcnow_iso(), **payload}
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def _profile_from_payload(payload: Mapping[str, Any], *, fallback_id: str) -> AccountProfile:
    account_id = str(payload.get("account_id") or payload.get("id") or fallback_id)
    broker_id = str(payload.get("broker_id") or payload.get("broker") or "unknown")
    mode = str(payload.get("mode") or "paper")
    base_currency = str(payload.get("base_currency") or "JPY")
    leverage = float(payload.get("leverage") or 1.0)
    status = str(payload.get("status") or "active")
    data_source = payload.get("data_source")
    update_interval = payload.get("update_interval")
    notes = payload.get("notes")
    if not account_id:
        raise ValueError("account_id missing")
    return AccountProfile(
        broker_id=broker_id,
        account_id=account_id,
        mode=mode,
        base_currency=base_currency,
        leverage=leverage,
        status=status,
        data_source=str(data_source) if data_source is not None else None,
        update_interval=int(update_interval) if update_interval is not None else None,
        notes=str(notes) if notes is not None else None,
    )


def _load_snapshot(
    path: Path, *, account_id: str, fmt: str, tz: str | None
) -> AccountSnapshot:
    if fmt == "csv":
        rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
        if not rows:
            raise ValueError("CSV snapshot is empty")
        payload = rows[0]
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    snapshot = _snapshot_from_payload(payload, account_id=account_id, tz=tz)
    return snapshot


def _snapshot_from_payload(
    payload: Mapping[str, Any], *, account_id: str | None = None, tz: str | None = None
) -> AccountSnapshot:
    resolved_id = account_id or str(payload.get("account_id") or payload.get("id") or "unknown")
    ts = payload.get("ts") or payload.get("timestamp") or _utcnow_iso()
    ts = _coerce_ts(ts, tz=tz)
    balance = float(payload.get("balance") or 0.0)
    equity = float(payload.get("equity") or balance)
    margin_used = float(payload.get("margin_used") or payload.get("margin") or 0.0)
    free_margin = float(payload.get("free_margin") or payload.get("free") or (equity - margin_used))
    floating_pnl = payload.get("floating_pnl")
    swap = payload.get("swap")
    status = str(payload.get("status") or "ok")
    positions_payload = payload.get("positions")
    positions = []
    if isinstance(positions_payload, list):
        for entry in positions_payload:
            if not isinstance(entry, Mapping):
                continue
            positions.append(
                PositionRecord(
                    symbol=str(entry.get("symbol") or ""),
                    side=str(entry.get("side") or ""),
                    lots=float(entry.get("lots") or 0.0),
                    avg_price=float(entry.get("avg_price") or 0.0),
                    unrealized_pnl=_coerce_optional_float(entry.get("unrealized_pnl")),
                    open_ts=str(entry.get("open_ts")) if entry.get("open_ts") else None,
                    tags=list(entry.get("tags") or []),
                )
            )
    open_positions_raw = payload.get("open_positions")
    if open_positions_raw is None:
        open_positions = len(positions) if positions_payload is not None else 0
    elif isinstance(open_positions_raw, list):
        open_positions = len(open_positions_raw)
    else:
        try:
            open_positions = int(open_positions_raw)
        except (TypeError, ValueError):
            open_positions = len(positions) if positions else 0
    return AccountSnapshot(
        account_id=resolved_id,
        ts=ts,
        balance=balance,
        equity=equity,
        margin_used=margin_used,
        free_margin=free_margin,
        open_positions=open_positions,
        floating_pnl=_coerce_optional_float(floating_pnl),
        swap=_coerce_optional_float(swap),
        status=status,
        positions=positions or None,
    )


def _snapshot_summary(snapshot: AccountSnapshot) -> dict[str, Any]:
    free_margin_pct = (snapshot.free_margin / snapshot.equity * 100.0) if snapshot.equity else 0.0
    drawdown_pct = ((snapshot.balance - snapshot.equity) / snapshot.balance * 100.0) if snapshot.balance else 0.0
    return {
        "account_id": snapshot.account_id,
        "ts": snapshot.ts,
        "balance": snapshot.balance,
        "equity": snapshot.equity,
        "margin_used": snapshot.margin_used,
        "free_margin": snapshot.free_margin,
        "free_margin_pct": round(free_margin_pct, 2),
        "drawdown_pct": round(drawdown_pct, 2),
        "open_positions": snapshot.open_positions,
        "status": snapshot.status,
    }


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _coerce_ts(value: Any, *, tz: str | None) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    token = str(value)
    parsed = _parse_ts(token)
    if parsed:
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_resolve_tz(tz))
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    now = datetime.now(timezone.utc)
    return now.isoformat().replace("+00:00", "Z")


def _coerce_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _slugify(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _resolve_tz(tz: str | None) -> timezone:
    if not tz:
        return timezone.utc
    try:
        return ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        return timezone.utc


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "AccountProfile",
    "AccountSnapshot",
    "PositionRecord",
    "AccountAlert",
    "AggregatedState",
    "AccountAggregator",
]
