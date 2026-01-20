"""Reporting helpers for `tradectl report` commands (see §17.9)."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml
import pandas as pd

from src.interfaces.cli import tickets as tickets_actions
from src.benchmark import BenchmarkReplayService
from src.journal import TradeJournalService
from src.reporter.attribution import AttributionEngine, DEFAULT_ATTRIBUTION_METRICS
from src.reporter.generator import ManualCsvSummary, ReportGenerator, RiskSummaryStub
from src.funding import load_funding_csv
from src.reporter.kpi import compute_kpi_from_equity, compute_kpi_from_returns
from src.governance.model_risk import ModelRiskRegisterService, ModelRiskSchemaError

logger = logging.getLogger(__name__)

__all__ = ["weekly", "daily", "performance"]

DEFAULT_WEEKLY_DIR = Path("reports/weekly")
DEFAULT_DAILY_DIR = Path("reports/daily")
DEFAULT_JOURNAL_EXPORT_DIR = Path("reports/journal")
DEFAULT_KPI_BASE = Path("reports/research/m1_baseline")
DEFAULT_RETURNS_PATH = Path("reports/performance/paper/returns.parquet")
DEFAULT_EQUITY_PATH = Path("reports/performance/paper/equity.parquet")
DEFAULT_BACKTEST_RETURNS_PATH = Path("reports/performance/backtest/returns.parquet")
DEFAULT_BACKTEST_EQUITY_PATH = Path("reports/performance/backtest/equity.parquet")
DEFAULT_PERFORMANCE_SNAPSHOT = Path("metrics") / "performance_snapshot.jsonl"
DEFAULT_PERFORMANCE_REPORT = Path("reports") / "performance" / "latest.md"
DEFAULT_KILL_SWITCH_LOG = Path("logs/events/risk.kill_switch.jsonl")
DEFAULT_KILL_SWITCH_LOG_ALT = Path("logs/risk/kill_switch_events.jsonl")
DEFAULT_RISK_DECISION_LOG = Path("logs/events/risk.decision.jsonl")
DEFAULT_SPREAD_METRICS = Path("metrics/spread_cooldown.jsonl")
DEFAULT_INGESTION_METRICS = Path("metrics/data_ingestion_sla.jsonl")
DEFAULT_RESYNC_LOG = Path("logs/resync/resync_events.jsonl")
DEFAULT_MANUAL_CSV_JOBS = Path("data/manual_fallback/jobs/jobs.jsonl")
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")
DEFAULT_WORKFLOW_METRICS = Path("metrics/trader_workflow.jsonl")
DEFAULT_COACHING_INSIGHTS = Path("metrics/coaching_insights.jsonl")
DEFAULT_COMPLIANCE_REGRESSION = Path("metrics/compliance_regression.json")
DEFAULT_DEGRADATION_METRICS = Path("metrics/degradation_playbook.jsonl")
DEFAULT_FUNDING_STATE = Path("data") / "state" / "funding_state.json"
DEFAULT_RISK_POLICY = Path("config") / "risk_policy.yaml"
DEFAULT_RISK_METRICS = Path("metrics/risk.jsonl")
DEFAULT_RISK_THRESHOLD_DIR = Path("reports") / "risk"


@dataclass(slots=True)
class RiskSummary:
    status: str = "unknown"
    summary: str = "n/a"

    def to_context(self) -> dict[str, object]:
        return {"risk_summary_status": self.status, "risk_summary": self.summary}


def _append_jsonl(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _read_jsonl_tail(path: Path, *, limit: int) -> list[Mapping[str, object]]:
    if not path.exists():
        return []
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return []
    records: list[Mapping[str, object]] = []
    for line in lines[-limit:]:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _summarize_kill_switch_history(path: Path = DEFAULT_KILL_SWITCH_LOG) -> str:
    entries = _read_jsonl_tail(path, limit=100)
    if not entries:
        return "n/a"
    states: list[str] = []
    for entry in entries:
        event = str(entry.get("event") or "")
        if event.startswith("kill_switch."):
            states.append(event.split(".", 1)[1])
        elif entry.get("state"):
            states.append(str(entry.get("state")))
    if not states:
        return "n/a"
    counts: dict[str, int] = {}
    for state in states:
        counts[state] = counts.get(state, 0) + 1
    last_state = states[-1]
    counts_str = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    return f"last={last_state}; counts: {counts_str}"


def _summarize_spread_cooldown(path: Path = DEFAULT_SPREAD_METRICS) -> str:
    entries = _read_jsonl_tail(path, limit=200)
    if not entries:
        return "n/a"
    counts: dict[str, int] = {}
    last_entry = entries[-1]
    for entry in entries:
        status = entry.get("status")
        if status is None:
            continue
        status_text = str(status)
        counts[status_text] = counts.get(status_text, 0) + 1
    if not counts:
        return "n/a"
    last_status = last_entry.get("status") or "unknown"
    last_symbol = last_entry.get("symbol") or "*"
    last_reason = last_entry.get("cooldown_reason") or "n/a"
    counts_str = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    return f"last={last_symbol}:{last_status} ({last_reason}); counts: {counts_str}"


def _summarize_data_quality(path: Path = DEFAULT_INGESTION_METRICS) -> str:
    entries = _read_jsonl_tail(path, limit=200)
    if not entries:
        return "n/a"
    flags: list[int] = []
    for entry in entries:
        if "quality_flag" in entry:
            try:
                flags.append(int(entry["quality_flag"]))
            except (TypeError, ValueError):
                continue
    if not flags:
        return "n/a"
    last_flag = flags[-1]
    flagged = sum(1 for flag in flags if flag > 0)
    label_map = {0: "ok", 1: "missing_bars", 2: "dup_bars", 3: "out_of_order", 4: "ts_mismatch"}
    last_label = label_map.get(last_flag, f"flag_{last_flag}")
    return f"last={last_flag} ({last_label}); flagged={flagged}/{len(flags)}"


def _summarize_degradation_playbook(
    path: Path = DEFAULT_DEGRADATION_METRICS,
) -> str:
    entries = _read_jsonl_tail(path, limit=200)
    if not entries:
        return "n/a"
    counts: dict[str, int] = {}
    for entry in entries:
        status = entry.get("status")
        if status is None:
            continue
        status_text = str(status)
        counts[status_text] = counts.get(status_text, 0) + 1
    last = entries[-1]
    last_status = last.get("status") or "unknown"
    last_scenario = last.get("scenario_id") or "unknown"
    counts_str = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    return f"last={last_scenario}:{last_status}; counts: {counts_str}"


def _summarize_resync(path: Path = DEFAULT_RESYNC_LOG) -> str:
    entries = _read_jsonl_tail(path, limit=200)
    if not entries:
        return "n/a"
    selected: Mapping[str, object] | None = None
    for entry in reversed(entries):
        if entry.get("event") == "resync.completed":
            selected = entry
            break
    if selected is None:
        selected = entries[-1]
    payload = selected.get("payload") if isinstance(selected, Mapping) else None
    payload = payload if isinstance(payload, Mapping) else selected
    catch_up_lag = payload.get("catch_up_lag_minutes")
    elapsed = payload.get("catch_up_elapsed_sec")
    manual_csv_required = payload.get("manual_csv_required")
    failover_used = payload.get("failover_used") or []
    latency_status = payload.get("latency_status")
    resync_latency_ratio = payload.get("resync_latency_ratio")
    summary = [
        f"lag={catch_up_lag}m" if catch_up_lag is not None else "lag=n/a",
        f"elapsed={elapsed}s" if elapsed is not None else "elapsed=n/a",
        f"manual_csv={manual_csv_required}",
        f"failover={len(failover_used)}",
    ]
    if latency_status is not None:
        summary.append(f"latency={latency_status}")
    if resync_latency_ratio is not None:
        summary.append(f"ratio={resync_latency_ratio:.2f}")
    return ", ".join(summary)


def _summarize_model_risk(*, profile: str) -> str:
    if not _read_feature_flag("governance.model_risk_register_enabled", profile=profile):
        return "deferred"
    service = ModelRiskRegisterService()
    try:
        register = service.load(Path("docs/governance/model_risk_register.md"))
    except ModelRiskSchemaError:
        return "model risk register unreadable"
    if not register.entries:
        return "- No model risk entries"
    pending = [entry.strategy_id for entry in register.entries if entry.status == "pending"]
    expired = [entry.strategy_id for entry in register.entries if entry.status == "expired"]
    blocked = [entry.strategy_id for entry in register.entries if entry.status == "blocked"]
    lines = []
    if pending:
        lines.append(f"- Pending: {', '.join(pending)}")
    if expired:
        lines.append(f"- Expired: {', '.join(expired)}")
    if blocked:
        lines.append(f"- Blocked: {', '.join(blocked)}")
    return "\n".join(lines) if lines else "- Approved only"


def _summarize_manual_csv(path: Path = DEFAULT_MANUAL_CSV_JOBS) -> str:
    entries = _read_jsonl_tail(path, limit=500)
    if not entries:
        return "n/a"
    counts: dict[str, int] = {}
    for entry in entries:
        status = entry.get("status") or "unknown"
        status_text = str(status)
        counts[status_text] = counts.get(status_text, 0) + 1
    last_entry = entries[-1]
    last_job = last_entry.get("job_id") or "unknown"
    last_status = last_entry.get("status") or "unknown"
    counts_str = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    return f"last={last_job} ({last_status}); counts: {counts_str}"


def _summarize_ops_worklog(path: Path = DEFAULT_OPS_WORKLOG, *, limit: int = 5) -> str:
    entries = _read_jsonl_tail(path, limit=limit)
    if not entries:
        return "- n/a"
    lines: list[str] = []
    for entry in entries:
        ts = entry.get("timestamp") or entry.get("ts") or "unknown"
        task = entry.get("task") or entry.get("action") or "unknown"
        actor = entry.get("actor") or entry.get("owner") or "unknown"
        note = entry.get("notes") or entry.get("note") or entry.get("ticket_id") or ""
        suffix = f" ({note})" if note else ""
        lines.append(f"- {ts} {task} {actor}{suffix}")
    return "\n".join(lines)


def _summarize_coaching(
    metrics_path: Path = DEFAULT_WORKFLOW_METRICS,
    insights_path: Path = DEFAULT_COACHING_INSIGHTS,
) -> str:
    summary = _read_last_event(metrics_path, "trader_workflow.summary")
    if not summary:
        return "n/a"
    parts: list[str] = []
    latency = summary.get("avg_approval_latency_sec")
    if latency is not None:
        parts.append(f"approval_latency_sec={latency:.1f}")
    checklist = summary.get("checklist_completion_rate")
    if checklist is not None:
        parts.append(f"checklist_completion_rate={checklist:.2f}")
    guarded = summary.get("guarded_time_ratio")
    if guarded is not None:
        parts.append(f"guarded_time_ratio={guarded:.2f}")
    mistake = summary.get("mistake_rate")
    if mistake is not None:
        parts.append(f"mistake_rate={mistake:.2f}")
    if insights_path.exists():
        entries = _read_jsonl_tail(insights_path, limit=200)
        over_threshold = sum(1 for entry in entries if entry.get("status") == "over_threshold")
        parts.append(f"over_threshold={over_threshold}")
    return "; ".join(parts) if parts else "n/a"


def _summarize_compliance_regression(path: Path = DEFAULT_COMPLIANCE_REGRESSION) -> str:
    if not path.exists():
        return "n/a"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "n/a"
    return (
        "violations={min_distance_violations}/{freeze_level_violations}, "
        "drop_pct={proposal_drop_pct}, throttle={throttle_triggered}".format(
            min_distance_violations=payload.get("min_distance_violations", "n/a"),
            freeze_level_violations=payload.get("freeze_level_violations", "n/a"),
            proposal_drop_pct=payload.get("proposal_drop_pct", "n/a"),
            throttle_triggered=payload.get("throttle_triggered", "n/a"),
        )
    )


def _read_last_event(path: Path, event_name: str) -> Mapping[str, object] | None:
    if not path.exists():
        return None
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return None
    for raw in reversed(lines):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if payload.get("event") == event_name:
            return payload
    return None


def _load_risk_thresholds(
    profile: str, *, path: Path = DEFAULT_RISK_POLICY
) -> Mapping[str, float]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    profiles = payload.get("profiles") if isinstance(payload, dict) else {}
    profile_cfg = {}
    if isinstance(profiles, Mapping):
        profile_cfg = profiles.get(profile) or profiles.get("m1_baseline") or {}
    kill_switch = profile_cfg.get("kill_switch") if isinstance(profile_cfg, Mapping) else {}
    drawdown = kill_switch.get("drawdown_threshold_pct") if isinstance(kill_switch, Mapping) else {}
    risk_limits = profile_cfg.get("risk_limits") if isinstance(profile_cfg, Mapping) else {}
    return {
        "daily_drawdown_pct": float(drawdown.get("daily", 0.0)) if isinstance(drawdown, Mapping) else 0.0,
        "weekly_drawdown_pct": float(drawdown.get("weekly", 0.0)) if isinstance(drawdown, Mapping) else 0.0,
        "capital_floor_pct": float(kill_switch.get("capital_floor_pct_of_base", 0.0))
        if isinstance(kill_switch, Mapping)
        else 0.0,
        "r_eff_soft": float(risk_limits.get("exposure_r_eff_soft_stop", 0.0))
        if isinstance(risk_limits, Mapping)
        else 0.0,
        "r_eff_hard": float(risk_limits.get("exposure_r_eff_hard_stop", 0.0))
        if isinstance(risk_limits, Mapping)
        else 0.0,
    }


def _extract_risk_metrics(metrics_path: Path = DEFAULT_RISK_METRICS) -> Mapping[str, float]:
    entries = _read_jsonl_tail(metrics_path, limit=50)
    if not entries:
        return {}
    latest = entries[-1]
    metrics: dict[str, float] = {}
    for key in ("daily_drawdown_pct", "weekly_drawdown_pct", "equity_pct_of_base", "exposure_r_eff"):
        value = latest.get(key)
        try:
            if value is not None:
                metrics[key] = float(value)
        except (TypeError, ValueError):
            continue
    return metrics


def _find_threshold_change_doc(base_dir: Path = DEFAULT_RISK_THRESHOLD_DIR) -> Path | None:
    if not base_dir.exists():
        return None
    candidates = sorted(base_dir.glob("threshold_change_*.md"))
    if not candidates:
        return None
    return candidates[-1]


def _summarize_risk_summary(
    *,
    profile: str,
    risk_decision_log: Path = DEFAULT_RISK_DECISION_LOG,
    kill_switch_log: Path = DEFAULT_KILL_SWITCH_LOG,
    risk_policy_path: Path = DEFAULT_RISK_POLICY,
    risk_metrics_path: Path = DEFAULT_RISK_METRICS,
) -> RiskSummary:
    thresholds = _load_risk_thresholds(profile, path=risk_policy_path)
    kill_entries = _read_jsonl_tail(kill_switch_log, limit=200)
    if not kill_entries:
        kill_entries = _read_jsonl_tail(DEFAULT_KILL_SWITCH_LOG_ALT, limit=200)
    kill_states: list[str] = []
    for entry in kill_entries:
        event = entry.get("event") or ""
        if isinstance(event, str) and event.startswith("kill_switch."):
            kill_states.append(event.split(".", 1)[1])
        elif entry.get("state"):
            kill_states.append(str(entry.get("state")))
    kill_counts: dict[str, int] = {}
    for state in kill_states:
        kill_counts[state] = kill_counts.get(state, 0) + 1
    last_kill = kill_states[-1] if kill_states else None

    decision_entries = _read_jsonl_tail(risk_decision_log, limit=200)
    last_decision: Mapping[str, object] | None = None
    for entry in reversed(decision_entries):
        decision = entry.get("decision")
        if isinstance(decision, Mapping):
            last_decision = decision
            break
    decision_state = {
        "board_mode": "unknown",
        "kill_switch_state": "none",
        "reduce_only": False,
        "reason": None,
    }
    if last_decision is not None:
        decision_state = {
            "board_mode": str(last_decision.get("board_mode") or "unknown"),
            "kill_switch_state": str(last_decision.get("kill_switch_state") or "none"),
            "reduce_only": bool(last_decision.get("reduce_only") or False),
            "reason": last_decision.get("reason"),
        }

    metrics = _extract_risk_metrics(risk_metrics_path)
    summary_parts: list[str] = []
    if last_decision is not None:
        reason = f" reason={decision_state['reason']}" if decision_state["reason"] else ""
        summary_parts.append(
            "decision="
            f"{decision_state['board_mode']}/"
            f"{decision_state['kill_switch_state']}/"
            f"reduce_only={decision_state['reduce_only']}{reason}"
        )
    if kill_counts:
        counts = ", ".join(f"{key}={kill_counts[key]}" for key in sorted(kill_counts))
        summary_parts.append(f"kill_switch_last={last_kill}; counts: {counts}")
    if thresholds:
        summary_parts.append(
            "thresholds="
            f"daily={thresholds.get('daily_drawdown_pct', 0):g}%,"
            f"weekly={thresholds.get('weekly_drawdown_pct', 0):g}%,"
            f"r_eff={thresholds.get('r_eff_soft', 0):g}/{thresholds.get('r_eff_hard', 0):g},"
            f"capital_floor={thresholds.get('capital_floor_pct', 0):g}%"
        )
    if metrics:
        metric_parts = []
        if "daily_drawdown_pct" in metrics:
            metric_parts.append(f"daily_dd={metrics['daily_drawdown_pct']:.2f}%")
        if "weekly_drawdown_pct" in metrics:
            metric_parts.append(f"weekly_dd={metrics['weekly_drawdown_pct']:.2f}%")
        if "equity_pct_of_base" in metrics:
            metric_parts.append(f"equity={metrics['equity_pct_of_base']:.2f}%")
        if "exposure_r_eff" in metrics:
            metric_parts.append(f"r_eff={metrics['exposure_r_eff']:.2f}")
        summary_parts.append("metrics=" + ", ".join(metric_parts))
    threshold_doc = _find_threshold_change_doc()
    if threshold_doc:
        summary_parts.append(f"threshold_change={threshold_doc.as_posix()}")

    status = "unknown"
    alert_states = {"hard_stop", "soft_stop"}
    if decision_state["kill_switch_state"] in alert_states or last_kill in alert_states:
        status = "alert"
    elif decision_state["reduce_only"] or decision_state["board_mode"] in {"guarded", "halted"}:
        status = "watch"
    elif summary_parts:
        status = "ok"

    summary_text = "; ".join(summary_parts) if summary_parts else "n/a"
    return RiskSummary(status=status, summary=summary_text)


def _resolve_template(profile: str, template: Path | None) -> Path:
    if template is not None:
        return template
    candidate = Path("src") / "reporter" / "templates" / f"weekly_{profile}.md"
    docs_candidate = Path("docs") / "templates" / "reports" / f"weekly_{profile}.md"
    if candidate.exists():
        return candidate
    if docs_candidate.exists():
        return docs_candidate
    return Path("src") / "reporter" / "templates" / "weekly_m1_core.md"


def _read_feature_flag(
    flag: str, *, profile: str, path: Path = Path("config/feature_flags.yaml")
) -> bool:
    if not path.exists():
        return False
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    defaults = payload.get("defaults") or {}
    profile_defaults = defaults.get(profile)
    if not isinstance(profile_defaults, dict):
        return False
    return bool(profile_defaults.get(flag, False))


def _load_stress_runs(stress_dir: Path) -> list[Mapping[str, object]]:
    if not stress_dir.exists():
        return []
    runs: list[Mapping[str, object]] = []
    for path in sorted(stress_dir.glob("*_report.md")):
        summary = ""
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    summary = line.strip("# ").strip()
                    break
        except OSError:
            summary = ""
        scenario = path.stem.replace("_report", "")
        runs.append(
            {"scenario": scenario, "status": "ok", "summary": summary, "artifacts": [str(path)]}
        )
    return runs


def _summarize_risk_envelope_delta(
    *,
    envelope_dir: Path = Path("reports") / "risk" / "envelopes",
    policy_path: Path = Path("config") / "risk_policy.yaml",
) -> str:
    if not envelope_dir.exists():
        return "no envelope updates"
    candidates = sorted(envelope_dir.glob("envelope_*.yaml"), reverse=True)
    if not candidates:
        return "no envelope updates"
    try:
        envelope = yaml.safe_load(candidates[0].read_text(encoding="utf-8")) or {}
    except Exception:
        return "envelope unreadable"
    if not policy_path.exists():
        return "risk policy missing"
    try:
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return "risk policy unreadable"
    profile = "m1_baseline"
    profiles = policy.get("profiles") if isinstance(policy, dict) else None
    profile_cfg = profiles.get(profile, {}) if isinstance(profiles, dict) else {}
    risk_limits = profile_cfg.get("risk_limits", {}) if isinstance(profile_cfg, dict) else {}
    kill_switch = profile_cfg.get("kill_switch", {}) if isinstance(profile_cfg, dict) else {}
    drawdown = kill_switch.get("drawdown_threshold_pct", {}) if isinstance(kill_switch, dict) else {}
    current = {
        "daily_loss": drawdown.get("daily"),
        "weekly_loss": drawdown.get("weekly"),
        "margin_warn": risk_limits.get("margin_warn"),
        "margin_throttle": risk_limits.get("margin_throttle"),
    }
    recommended = envelope.get("recommended_thresholds") or {}
    lines = []
    for key, value in recommended.items():
        if key not in current:
            continue
        lines.append(f"- {key}: {current.get(key)} -> {value}")
    if not lines:
        return "no threshold deltas"
    banner = "[RISK ENVELOPE UPDATED]"
    return "\n".join([banner, *lines])


def _format_kpi_value(value: object) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.4f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return "n/a"


def _load_latest_kpis(base_dir: Path = DEFAULT_KPI_BASE) -> tuple[dict[str, object], Path | None]:
    if not base_dir.exists():
        return {"sharpe": "n/a", "max_dd": "n/a", "win_rate": "n/a", "cum_r": "n/a"}, None
    candidates = sorted(
        base_dir.glob("metrics_*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not candidates:
        return {"sharpe": "n/a", "max_dd": "n/a", "win_rate": "n/a", "cum_r": "n/a"}, None
    try:
        payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"sharpe": "n/a", "max_dd": "n/a", "win_rate": "n/a", "cum_r": "n/a"}, None
    metrics = payload.get("metrics") or {}
    return {
        "sharpe": _format_kpi_value(metrics.get("sharpe_all")),
        "max_dd": _format_kpi_value(metrics.get("max_drawdown_all")),
        "win_rate": _format_kpi_value(metrics.get("win_rate")),
        "cum_r": _format_kpi_value(metrics.get("pf_all")),
    }, candidates[0]


def _resolve_metric_state(*, profile: str, kpi_source: Path | None) -> str:
    if profile != "paper" or kpi_source is None or not kpi_source.exists():
        return "confirmed"
    try:
        if kpi_source.suffix.lower() == ".parquet":
            df = pd.read_parquet(kpi_source)
        else:
            df = pd.read_csv(kpi_source)
    except Exception:
        return "confirmed"
    if df.empty:
        return "provisional"
    if "timestamp" in df.columns:
        series = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").dropna()
        if series.empty:
            return "provisional"
        start = series.min()
        end = series.max()
    else:
        try:
            series = pd.to_datetime(df.index, utc=True, errors="coerce")
        except Exception:
            return "confirmed"
        series = series.dropna()
        if series.empty:
            return "provisional"
        start = series.min()
        end = series.max()
    days = (end - start).days
    return "provisional" if days < 90 else "confirmed"


def _summarize_funding(
    *,
    state_path: Path = DEFAULT_FUNDING_STATE,
    max_pairs: int = 5,
) -> str:
    if not state_path.exists():
        return "funding_state missing"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "funding_state unreadable"
    csv_path = state.get("csv_path")
    if not csv_path:
        return "funding_state missing csv_path"
    curve = load_funding_csv(csv_path)
    if not curve.swap_rates:
        return "swap rates not found"
    today = date.today()
    lines = []
    for pair, rate in sorted(curve.swap_rates.items())[:max_pairs]:
        long_penalty = curve.swap_penalty(pair=pair, direction="long", session_date=today)
        short_penalty = curve.swap_penalty(pair=pair, direction="short", session_date=today)
        lines.append(
            f"- {pair}: long={rate.swap_long}, short={rate.swap_short}, "
            f"triple_day={rate.triple_day}, penalty_long={long_penalty}, "
            f"penalty_short={short_penalty}"
        )
    if len(curve.swap_rates) > max_pairs:
        lines.append(f"- ... {len(curve.swap_rates) - max_pairs} more pairs")
    return "\n".join(lines)


def _summarize_benchmark(*, profile: str, with_benchmark: bool) -> str:
    if not with_benchmark and not _read_feature_flag("benchmark.replay", profile=profile):
        return "deferred"
    try:
        result = BenchmarkReplayService().replay(
            window="90d",
            mode="paper" if profile != "live" else "live",
            providers=None,
            export_path=None,
            fail_on_gap=False,
        )
    except Exception as exc:  # noqa: BLE001
        return f"benchmark replay failed: {exc}"
    lines = [
        f"- Status: {result.status}",
        f"- Provider: {result.symbol or 'unknown'}",
        f"- Missing Ratio: {result.missing_ratio:.2%}",
    ]
    diff = result.diff_metrics
    if diff:
        lines.append(
            "- Diff: "
            + ", ".join(
                f"{key}={value}" for key, value in diff.items() if value is not None
            )
        )
    if result.recommendations:
        lines.append("- Recommendations: " + "; ".join(result.recommendations))
    return "\n".join(lines)


def weekly(
    profile: str,
    *,
    week: str | None = None,
    template_path: Path | None = None,
    stress_runs: Sequence[Mapping[str, object]] | None = None,
    stress_dir: Path = Path("reports") / "stress",
    journal_entries: Sequence[Mapping[str, object]] | None = None,
    journal_path: Path = Path("logs") / "journal" / "journal_entries.db",
    dry_run: bool = False,
    output_path: Path | None = None,
    kpi: Mapping[str, object] | None = None,
    kpi_base: Path = DEFAULT_KPI_BASE,
    returns_path: Path = DEFAULT_RETURNS_PATH,
    equity_path: Path = DEFAULT_EQUITY_PATH,
    journal_export_dir: Path | None = None,
    tickets: Sequence[Mapping[str, object]] | None = None,
    with_benchmark: bool = False,
    with_attribution: bool = False,
    attribution_window: str = "7d",
    attribution_metrics_path: Path = DEFAULT_ATTRIBUTION_METRICS,
    attribution_report_dir: Path = Path("reports") / "attribution",
) -> dict[str, object]:
    """Generate a weekly report with the M1 Core template."""

    iso_week = week or date.today().strftime("%G-W%V")
    effective_template = _resolve_template(profile, template_path)
    extended_blocks = False
    if template_path is None and _read_feature_flag(
        "reporter.enable_extended_blocks", profile=profile
    ):
        extended_blocks = True
        extended_candidate = Path("src") / "reporter" / "templates" / "weekly_m1_core_extended.md"
        docs_extended = Path("docs") / "templates" / "reports" / "weekly_m1_core_extended.md"
        if extended_candidate.exists():
            effective_template = extended_candidate
        elif docs_extended.exists():
            effective_template = docs_extended
    tickets_payload = (
        list(tickets)
        if tickets is not None
        else list(tickets_actions.list_tickets(include_history=False, json_output=False))
    )
    stress_payload = list(stress_runs) if stress_runs is not None else _load_stress_runs(stress_dir)
    journal_service = TradeJournalService(path=journal_path)
    journal_enabled = _read_feature_flag("journal.enabled", profile=profile)
    journal_weekly_summary = _read_feature_flag("journal.weekly_summary", profile=profile)
    if journal_entries is not None:
        journal_payload = list(journal_entries)
    elif journal_enabled and journal_weekly_summary:
        journal_payload = journal_service.list(week=iso_week)
    else:
        journal_payload = []
    journal_export: str | None = None
    if not dry_run and journal_enabled and journal_weekly_summary:
        export_path = journal_service.export_weekly(
            week=iso_week, output_dir=journal_export_dir or DEFAULT_JOURNAL_EXPORT_DIR
        )
        journal_export = str(export_path)
    kpi_source: Path | None = None
    kpi_payload = dict(kpi) if kpi is not None else _load_latest_kpis(kpi_base)[0]
    if kpi is None:
        returns_candidates = [returns_path, DEFAULT_BACKTEST_RETURNS_PATH]
        equity_candidates = [equity_path, DEFAULT_BACKTEST_EQUITY_PATH]
        for candidate in returns_candidates:
            if candidate.exists():
                try:
                    kpi_payload = compute_kpi_from_returns(candidate)
                    kpi_source = candidate
                    break
                except Exception:
                    continue
        if kpi_source is None:
            for candidate in equity_candidates:
                if candidate.exists():
                    try:
                        kpi_payload = compute_kpi_from_equity(candidate)
                        kpi_source = candidate
                        break
                    except Exception:
                        continue
    if kpi is None and kpi_source is None:
        _, latest_path = _load_latest_kpis(kpi_base)
        kpi_source = latest_path
    risk_summary = RiskSummaryStub()
    if extended_blocks:
        risk_summary = _summarize_risk_summary(profile=profile)
    manual_csv = ManualCsvSummary(summary=_summarize_manual_csv())
    extra_context = {}
    extra_context.update(risk_summary.to_context())
    extra_context.update(manual_csv.to_context())
    extra_context["model_risk_summary"] = _summarize_model_risk(profile=profile)
    extra_context["ops_worklog_excerpt"] = _summarize_ops_worklog()
    extra_context["coaching_summary"] = _summarize_coaching()
    extra_context["compliance_regression_summary"] = _summarize_compliance_regression()
    extra_context["degradation_summary"] = _summarize_degradation_playbook()
    extra_context["funding_summary"] = _summarize_funding()
    extra_context["benchmark_summary"] = _summarize_benchmark(
        profile=profile,
        with_benchmark=with_benchmark,
    )
    extra_context["risk_envelope_delta"] = _summarize_risk_envelope_delta()
    attribution_summary = "deferred"
    if with_attribution:
        engine = AttributionEngine(
            metrics_path=attribution_metrics_path,
            report_dir=attribution_report_dir,
        )
        attribution = engine.evaluate(window=attribution_window)
        attribution_summary = attribution.render_markdown(include_header=False)
    extra_context["attribution_summary"] = attribution_summary
    if extended_blocks:
        extra_context.update(
            {
                "kill_switch_history": _summarize_kill_switch_history(),
                "spread_cooldown_summary": _summarize_spread_cooldown(),
                "data_quality_summary": _summarize_data_quality(),
                "resync_summary": _summarize_resync(),
            }
        )
    else:
        extra_context.update(
            {
                "kill_switch_history": "deferred",
                "spread_cooldown_summary": "deferred",
                "data_quality_summary": "deferred",
                "resync_summary": "deferred",
            }
        )
    performance_snapshot = None
    if _read_feature_flag("reports.performance.enable", profile=profile):
        performance_snapshot = performance(
            profile=profile,
            output_path=None,
            metrics_path=DEFAULT_PERFORMANCE_SNAPSHOT,
            returns_path=returns_path,
            equity_path=equity_path,
            dry_run=dry_run,
        )
    if with_attribution and template_path is None:
        attribution_template = (
            Path("src") / "reporter" / "templates" / "weekly_m1_core_attribution.md"
        )
        if extended_blocks:
            extended_attribution = (
                Path("src") / "reporter" / "templates" / "weekly_m1_core_extended_attribution.md"
            )
            if extended_attribution.exists():
                effective_template = extended_attribution
        elif attribution_template.exists():
            effective_template = attribution_template
    summary = ReportGenerator().render_weekly_report(
        week=iso_week,
        tickets=tickets_payload,
        stress_runs=stress_payload,
        journal_entries=journal_payload,
        template_path=effective_template,
        kpi=kpi_payload,
        extra_context=extra_context,
    )
    output = output_path or (DEFAULT_WEEKLY_DIR / f"{iso_week}.md")
    if not dry_run:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(summary, encoding="utf-8")
    payload = {
        "status": "ok",
        "profile": profile,
        "week": iso_week,
        "path": str(output) if not dry_run else None,
        "ticket_summary": summary,
        "stress_runs": stress_payload,
        "journal_entries": journal_payload,
        "journal_export": journal_export,
        "benchmark_summary": extra_context.get("benchmark_summary"),
        "attribution_summary": extra_context.get("attribution_summary"),
        "kpi": kpi_payload,
        "kpi_source": str(kpi_source) if kpi_source else None,
        "performance_snapshot": performance_snapshot,
    }
    logger.info(
        "cli.report.weekly.completed",
        extra={"week": iso_week, "output": str(output), "dry_run": dry_run},
    )
    return payload


def performance(
    profile: str,
    *,
    output_path: Path | None = None,
    metrics_path: Path = DEFAULT_PERFORMANCE_SNAPSHOT,
    returns_path: Path = DEFAULT_RETURNS_PATH,
    equity_path: Path = DEFAULT_EQUITY_PATH,
    kpi: Mapping[str, object] | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    """Generate a performance snapshot and append metrics."""

    if not _read_feature_flag("reports.performance.enable", profile=profile):
        payload = {
            "timestamp": _utcnow_iso(),
            "status": "disabled",
            "profile": profile,
            "feature_flag": "reports.performance.enable",
            "metrics_path": str(metrics_path),
            "report_path": str(output_path or DEFAULT_PERFORMANCE_REPORT),
        }
        logger.info("cli.report.performance.disabled", extra={"profile": profile})
        return payload

    now = _utcnow_iso()
    kpi_payload = dict(kpi) if kpi is not None else None
    kpi_source: Path | None = None

    if kpi_payload is None:
        if returns_path.exists():
            kpi_payload = compute_kpi_from_returns(returns_path)
            kpi_source = returns_path
        elif equity_path.exists():
            kpi_payload = compute_kpi_from_equity(equity_path)
            kpi_source = equity_path
        else:
            kpi_payload = {"sharpe": "n/a", "max_dd": "n/a", "win_rate": "n/a", "cum_r": "n/a"}

    metric_state = _resolve_metric_state(profile=profile, kpi_source=kpi_source)
    payload = {
        "timestamp": now,
        "status": "ok",
        "profile": profile,
        "kpi": kpi_payload,
        "kpi_source": str(kpi_source) if kpi_source else None,
        "metric_state": metric_state,
    }

    if not dry_run:
        _append_jsonl(metrics_path, payload)
        report_path = output_path or DEFAULT_PERFORMANCE_REPORT
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(_render_performance_md(payload), encoding="utf-8")
        payload["path"] = str(report_path)
    else:
        payload["path"] = None

    payload["metrics_path"] = str(metrics_path)
    return payload


def _render_performance_md(payload: Mapping[str, object]) -> str:
    kpi = payload.get("kpi") or {}
    return "\n".join(
        [
            "# Performance Snapshot",
            "",
            f"- Timestamp: {payload.get('timestamp')}",
            f"- Profile: {payload.get('profile')}",
            f"- KPI Source: {payload.get('kpi_source') or 'n/a'}",
            f"- Metric State: {payload.get('metric_state') or 'confirmed'}",
            "",
            "## KPI",
            "",
            f"- Sharpe: {kpi.get('sharpe')}",
            f"- Max DD: {kpi.get('max_dd')}",
            f"- Win Rate: {kpi.get('win_rate')}",
            f"- Cumulative R: {kpi.get('cum_r')}",
            "",
        ]
    )


def daily(
    *,
    date: str,
    profile: str | None = None,
    out: str | Path | None = None,
    dry_run: bool = False,
    notes: Sequence[str] | None = None,
) -> dict[str, object]:
    """Generate a daily report placeholder."""

    output = Path(out) if out is not None else (DEFAULT_DAILY_DIR / f"{date}.md")
    lines = [
        f"# Daily Report {date}",
        "",
        f"- Profile: {profile or 'unspecified'}",
    ]
    for note in notes or ():
        lines.append(f"- Note: {note}")
    lines.append("- Status: draft")
    content = "\n".join(lines) + "\n"
    if not dry_run:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    payload = {
        "status": "ok",
        "date": date,
        "profile": profile,
        "path": str(output) if not dry_run else None,
        "content": content,
    }
    logger.info(
        "cli.report.daily.completed",
        extra={"date": date, "output": str(output), "dry_run": dry_run},
    )
    return payload
