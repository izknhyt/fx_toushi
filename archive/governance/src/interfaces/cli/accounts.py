"""Account aggregation CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from src.accounts.aggregator import AccountAggregator

DEFAULT_PROFILE_DIR = Path("accounts")
DEFAULT_SNAPSHOT_DIR = Path("reports") / "accounts"
DEFAULT_METRICS_PATH = Path("metrics") / "accounts_aggregator.jsonl"
DEFAULT_PORTFOLIO_DIR = Path("reports") / "performance" / "portfolio"

DEFAULT_PORTFOLIO_LOG = Path("jsonl") / "accounts" / "portfolio_state.jsonl"

__all__ = ["status", "ingest", "aggregate", "diff", "alerts", "coverage", "rebalance"]


def status(
    *,
    account: str | None = None,
    with_positions: bool = False,
    profile_dir: Path = DEFAULT_PROFILE_DIR,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    metrics_path: Path = DEFAULT_METRICS_PATH,
) -> Mapping[str, Any]:
    service = AccountAggregator(
        profile_dir=profile_dir,
        snapshot_dir=snapshot_dir,
        metrics_path=metrics_path,
    )
    profiles = service.load_profiles()
    snapshots = service.latest_snapshots()
    if account:
        profiles = [profile for profile in profiles if profile.account_id == account]
        snapshots = [snap for snap in snapshots if snap.account_id == account]
    payload = {
        "status": "ok",
        "profiles": [_profile_dict(profile) for profile in profiles],
        "snapshots": [snap.to_dict() for snap in snapshots]
        if with_positions
        else [_snapshot_brief(snap) for snap in snapshots],
    }
    return payload


def ingest(
    *,
    profile_id: str,
    path: Path,
    fmt: str = "json",
    tz: str | None = None,
    append: bool = False,
    profile_dir: Path = DEFAULT_PROFILE_DIR,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    metrics_path: Path = DEFAULT_METRICS_PATH,
) -> Mapping[str, Any]:
    service = AccountAggregator(
        profile_dir=profile_dir,
        snapshot_dir=snapshot_dir,
        metrics_path=metrics_path,
    )
    snapshot = service.ingest_snapshot(
        profile_id=profile_id,
        source_path=path,
        fmt=fmt,
        tz=tz,
        append=append,
    )
    return {"status": "ok", "snapshot": snapshot.to_dict()}


def aggregate(
    *,
    account_filter: Iterable[str] | None = None,
    export_md: Path | None = None,
    date_tag: str | None = None,
    portfolio_currency: str | None = None,
    persist: bool = False,
    include_variance: bool = False,
    profile_dir: Path = DEFAULT_PROFILE_DIR,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    metrics_path: Path = DEFAULT_METRICS_PATH,
) -> Mapping[str, Any]:
    service = AccountAggregator(
        profile_dir=profile_dir,
        snapshot_dir=snapshot_dir,
        metrics_path=metrics_path,
    )
    state = service.aggregate(
        account_filter=account_filter,
        portfolio_currency=portfolio_currency,
        persist=persist,
        date_tag=date_tag,
        include_variance=include_variance,
    )
    payload = {"status": "ok", "aggregate": state.to_dict()}
    if export_md:
        export_md.parent.mkdir(parents=True, exist_ok=True)
        export_md.write_text(_render_markdown(state), encoding="utf-8")
        payload["export_path"] = str(export_md)
    return payload


def diff(
    *,
    period_a: str,
    period_b: str,
    profile_dir: Path = DEFAULT_PROFILE_DIR,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    metrics_path: Path = DEFAULT_METRICS_PATH,
) -> Mapping[str, Any]:
    service = AccountAggregator(
        profile_dir=profile_dir,
        snapshot_dir=snapshot_dir,
        metrics_path=metrics_path,
    )
    payload = service.diff(period_a=period_a, period_b=period_b)
    return {"status": "ok", **payload}


def alerts(
    *,
    severity: str | None = None,
    ack: bool = False,
    profile_dir: Path = DEFAULT_PROFILE_DIR,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    metrics_path: Path = DEFAULT_METRICS_PATH,
) -> Mapping[str, Any]:
    service = AccountAggregator(
        profile_dir=profile_dir,
        snapshot_dir=snapshot_dir,
        metrics_path=metrics_path,
    )
    snapshots = service.latest_snapshots()
    entries = service.generate_alerts(snapshots)
    if severity:
        entries = [alert for alert in entries if alert.severity == severity]
    payload = {
        "status": "ok",
        "alerts": [alert.to_dict() for alert in entries],
        "acknowledged": ack,
    }
    return payload


def coverage(
    *,
    window_days: int = 30,
    portfolio_log: Path = DEFAULT_PORTFOLIO_LOG,
) -> Mapping[str, Any]:
    if not portfolio_log.exists():
        return {"status": "ok", "coverage_pct": 0.0, "entries": 0}
    lines = [line for line in portfolio_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    entries = len(lines)
    coverage_pct = 100.0 if entries > 0 else 0.0
    return {"status": "ok", "coverage_pct": coverage_pct, "entries": entries, "window_days": window_days}


def rebalance(
    *,
    plan_path: Path,
    dry_run: bool = False,
) -> Mapping[str, Any]:
    if not plan_path.exists():
        raise FileNotFoundError(str(plan_path))
    content = plan_path.read_text(encoding="utf-8")
    output_path = plan_path.with_name(f"rebalance_plan_{plan_path.stem}.md")
    output_path.write_text(content, encoding="utf-8")
    return {
        "status": "ok",
        "plan_path": str(plan_path),
        "output_path": str(output_path),
        "dry_run": dry_run,
    }


def _snapshot_brief(snapshot: Any) -> Mapping[str, Any]:
    return {
        "account_id": snapshot.account_id,
        "ts": snapshot.ts,
        "balance": snapshot.balance,
        "equity": snapshot.equity,
        "margin_used": snapshot.margin_used,
        "free_margin": snapshot.free_margin,
        "open_positions": snapshot.open_positions,
        "status": snapshot.status,
    }


def _profile_dict(profile: Any) -> Mapping[str, Any]:
    return {
        "account_id": profile.account_id,
        "broker": profile.broker,
        "mode": profile.mode,
        "base_currency": profile.base_currency,
        "weight": profile.weight,
        "margin_mode": profile.margin_mode,
        "max_leverage": profile.max_leverage,
        "is_hedge": profile.is_hedge,
        "statement_path": profile.statement_path,
        "import_schedule_cron": profile.import_schedule_cron,
        "status": profile.status,
        "tags": profile.tags,
        "notes": profile.notes,
    }


def _render_markdown(state: Any) -> str:
    lines = [
        "# Accounts Aggregate",
        "",
        f"- Generated at: {state.ts}",
        f"- Total equity: {state.total_equity}",
        f"- Total margin: {state.total_margin}",
        f"- R_eff total: {state.r_eff_total}",
        "",
        "## Accounts",
        "",
        "| Account | Equity | Margin | Free Margin | Drawdown% | Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in state.account_breakdown:
        lines.append(
            f"| {entry['account_id']} | {entry['equity']} | {entry['margin_used']} | {entry['free_margin']} | {entry['drawdown_pct']} | {entry['status']} |"
        )
    lines.append("")
    lines.append("## Alerts")
    lines.append("")
    if not state.alerts:
        lines.append("No alerts.")
        return "\n".join(lines) + "\n"
    lines.append("| Account | Severity | Reason | Metric | Value | Threshold | Runbook |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for alert in state.alerts:
        lines.append(
            f"| {alert.account_id} | {alert.severity} | {alert.reason} | {alert.metric} | {alert.value} | {alert.threshold} | {alert.runbook_ref} |"
        )
    return "\n".join(lines) + "\n"
