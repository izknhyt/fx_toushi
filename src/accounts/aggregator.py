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

DEFAULT_PROFILE_DIR = Path("accounts")
DEFAULT_SNAPSHOT_DIR = Path("reports") / "accounts"
DEFAULT_METRICS_PATH = Path("metrics") / "accounts_aggregator.jsonl"
DEFAULT_PORTFOLIO_DIR = Path("reports") / "performance" / "portfolio"
DEFAULT_PORTFOLIO_LOG = Path("jsonl") / "accounts" / "portfolio_state.jsonl"
DEFAULT_STATE_TEMPLATE = DEFAULT_PORTFOLIO_DIR / "templates" / "state.md"


@dataclass(slots=True)
class AccountProfile:
    account_id: str
    broker: str
    mode: str
    base_currency: str
    weight: float
    margin_mode: str
    max_leverage: float
    is_hedge: bool
    statement_path: str
    import_schedule_cron: str
    tags: list[str] | None = None
    notes: str | None = None
    status: str | None = None


@dataclass(slots=True)
class PositionRecord:
    symbol: str
    side: str
    lots: float
    avg_price: float
    unrealized_pnl: float | None = None
    open_ts: str | None = None
    tags: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "lots": self.lots,
            "avg_price": self.avg_price,
            "unrealized_pnl": self.unrealized_pnl,
            "open_ts": self.open_ts,
            "tags": list(self.tags or []),
        }


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
            "positions": [pos.to_dict() for pos in self.positions or []],
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
    base_currency: str
    total_equity: float
    total_margin_used: float
    r_eff_total: float
    account_breakdown: list[Mapping[str, Any]]
    alerts: list[AccountAlert]
    variance_flags: list[Mapping[str, Any]] | None = None

    @property
    def total_margin(self) -> float:
        return self.total_margin_used

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "base_currency": self.base_currency,
            "total_equity": self.total_equity,
            "total_margin": self.total_margin_used,
            "total_margin_used": self.total_margin_used,
            "r_eff_total": self.r_eff_total,
            "account_breakdown": list(self.account_breakdown),
            "alerts": [alert.to_dict() for alert in self.alerts],
            "variance_flags": list(self.variance_flags or []),
        }


class AccountAggregator:
    def __init__(
        self,
        *,
        profile_dir: Path = DEFAULT_PROFILE_DIR,
        snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        portfolio_dir: Path = DEFAULT_PORTFOLIO_DIR,
        portfolio_log: Path = DEFAULT_PORTFOLIO_LOG,
        state_template: Path = DEFAULT_STATE_TEMPLATE,
    ) -> None:
        self._profile_dir = profile_dir
        self._snapshot_dir = snapshot_dir
        self._metrics_path = metrics_path
        self._portfolio_dir = portfolio_dir
        self._portfolio_log = portfolio_log
        self._state_template = state_template

    def load_profiles(self) -> list[AccountProfile]:
        profile_root = _resolve_profile_root(self._profile_dir)
        if not profile_root.exists():
            return []
        profiles: list[AccountProfile] = []
        for path in sorted(profile_root.rglob("*.yaml")):
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
            if profile.broker == profile_id:
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
        self,
        *,
        account_filter: Iterable[str] | None = None,
        portfolio_currency: str | None = None,
        persist: bool = False,
        date_tag: str | None = None,
        include_variance: bool = False,
    ) -> AggregatedState:
        snapshots = self.latest_snapshots()
        if account_filter:
            allowed = {str(item) for item in account_filter}
            snapshots = [snap for snap in snapshots if snap.account_id in allowed]
        alerts = self.generate_alerts(snapshots)
        total_equity = sum(snap.equity for snap in snapshots)
        total_margin_used = sum(snap.margin_used for snap in snapshots)
        r_eff_total = total_margin_used / total_equity if total_equity else 0.0
        breakdown = [_snapshot_summary(snap) for snap in snapshots]
        base_currency = portfolio_currency or _resolve_base_currency(self.load_profiles())
        state = AggregatedState(
            ts=_utcnow_iso(),
            base_currency=base_currency,
            total_equity=round(total_equity, 2),
            total_margin_used=round(total_margin_used, 2),
            r_eff_total=round(r_eff_total, 4),
            account_breakdown=breakdown,
            alerts=alerts,
            variance_flags=[],
        )
        if include_variance:
            try:
                from src.risk.portfolio_exposure import PortfolioExposureAnalyzer

                analyzer = PortfolioExposureAnalyzer()
                state_payload = state.to_dict()
                state.variance_flags = analyzer.detect_variance(state_payload)
            except Exception:
                state.variance_flags = []
        self._append_metrics(
            {
                "event": "accounts.aggregate.updated",
                "total_equity": state.total_equity,
                "total_margin": state.total_margin_used,
                "r_eff_total": state.r_eff_total,
                "alerts_count": len(alerts),
            }
        )
        if persist:
            self._persist_state(state, date_tag=date_tag)
        return state

    def diff(self, *, period_a: str, period_b: str) -> dict[str, Any]:
        state_a = self._load_state(period_a)
        state_b = self._load_state(period_b)
        total_margin_a = state_a.get("total_margin_used", state_a.get("total_margin", 0.0))
        total_margin_b = state_b.get("total_margin_used", state_b.get("total_margin", 0.0))
        delta_equity = round(state_b["total_equity"] - state_a["total_equity"], 2)
        delta_margin = round(total_margin_b - total_margin_a, 2)
        payload = {
            "period_a": period_a,
            "period_b": period_b,
            "delta_equity": delta_equity,
            "delta_margin": delta_margin,
            "base_currency": state_b.get("base_currency"),
        }
        diff_path = self._portfolio_dir / f"diff_{period_a}_{period_b}.md"
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_path.write_text(_render_diff_markdown(payload), encoding="utf-8")
        self._append_metrics(
            {
                "event": "accounts.diff.generated",
                "period_a": period_a,
                "period_b": period_b,
                "delta_equity": delta_equity,
                "delta_margin": delta_margin,
            }
        )
        payload["diff_path"] = str(diff_path)
        return payload

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

    def _persist_state(self, state: AggregatedState, *, date_tag: str | None) -> None:
        date_token = date_tag or datetime.now(timezone.utc).strftime("%Y%m%d")
        self._portfolio_dir.mkdir(parents=True, exist_ok=True)
        json_path = self._portfolio_dir / f"portfolio_state_{date_token}.json"
        json_path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        report_path = self._portfolio_dir / f"portfolio_state_{date_token}.md"
        report_path.write_text(_render_state_markdown(state, date_token, self._state_template), encoding="utf-8")
        self._portfolio_log.parent.mkdir(parents=True, exist_ok=True)
        with self._portfolio_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(state.to_dict(), ensure_ascii=False))
            handle.write("\n")

    def _load_state(self, date_tag: str) -> dict[str, Any]:
        path = self._portfolio_dir / f"portfolio_state_{date_tag}.json"
        if not path.exists():
            raise FileNotFoundError(str(path))
        return json.loads(path.read_text(encoding="utf-8"))


def _profile_from_payload(payload: Mapping[str, Any], *, fallback_id: str) -> AccountProfile:
    account_id = str(payload.get("account_id") or payload.get("id") or fallback_id)
    broker = str(payload.get("broker") or payload.get("broker_id") or "unknown")
    mode = str(payload.get("mode") or "paper")
    base_currency = str(payload.get("base_currency") or "JPY")
    weight = float(payload.get("weight") or 1.0)
    margin_mode = str(payload.get("margin_mode") or "netting")
    max_leverage = float(payload.get("max_leverage") or payload.get("leverage") or 1.0)
    is_hedge = bool(payload.get("is_hedge", False))
    statement_path = str(payload.get("statement_path") or payload.get("data_source") or "")
    import_schedule_cron = str(payload.get("import_schedule_cron") or _cron_from_interval(payload.get("update_interval")))
    status = str(payload.get("status") or "active")
    notes = payload.get("notes")
    if not statement_path:
        raise ValueError("statement_path missing")
    if not account_id:
        raise ValueError("account_id missing")
    return AccountProfile(
        account_id=account_id,
        broker=broker,
        mode=mode,
        base_currency=base_currency,
        weight=weight,
        margin_mode=margin_mode,
        max_leverage=max_leverage,
        is_hedge=is_hedge,
        statement_path=statement_path,
        import_schedule_cron=import_schedule_cron,
        tags=list(payload.get("tags") or []),
        notes=str(notes) if notes is not None else None,
        status=status,
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


def _resolve_profile_root(profile_dir: Path) -> Path:
    if profile_dir.exists():
        return profile_dir
    fallback = Path("config") / "accounts"
    return fallback if fallback.exists() else profile_dir


def _resolve_base_currency(profiles: Iterable[AccountProfile]) -> str:
    for profile in profiles:
        if profile.base_currency:
            return profile.base_currency
    return "JPY"


def _cron_from_interval(interval: Any) -> str:
    if interval is None:
        return "0 0 * * *"
    try:
        minutes = int(interval)
    except (TypeError, ValueError):
        return "0 0 * * *"
    if minutes <= 0:
        return "0 0 * * *"
    return f"*/{minutes} * * * *"


def _render_state_markdown(state: AggregatedState, date_tag: str, template_path: Path) -> str:
    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
    else:
        template = (
            "# Portfolio State ({date})\n"
            "- base_currency: {base_currency}\n"
            "- total_equity: {total_equity}\n"
            "- total_margin_used: {total_margin_used}\n"
            "\n## Accounts\n{accounts}\n\n## Alerts\n{alerts}\n"
        )
    accounts_block = "\n".join(
        [f"- {entry['account_id']}: equity={entry['equity']}" for entry in state.account_breakdown]
    ) or "- n/a"
    alerts_block = "\n".join(
        [f"- {alert.account_id}: {alert.reason}" for alert in state.alerts]
    ) or "- n/a"
    return (
        template.format(
            date=date_tag,
            base_currency=state.base_currency,
            total_equity=state.total_equity,
            total_margin_used=state.total_margin_used,
            accounts=accounts_block,
            alerts=alerts_block,
        )
        + "\n"
    )


def _render_diff_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Portfolio Diff",
        f"- period_a: {payload['period_a']}",
        f"- period_b: {payload['period_b']}",
        f"- delta_equity: {payload['delta_equity']}",
        f"- delta_margin: {payload['delta_margin']}",
    ]
    return "\n".join(lines) + "\n"


__all__ = [
    "AccountProfile",
    "AccountSnapshot",
    "PositionRecord",
    "AccountAlert",
    "AggregatedState",
    "AccountAggregator",
]
