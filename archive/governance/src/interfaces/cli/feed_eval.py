"""CLI helpers for real-time feed evaluation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.core.health import HealthMonitor
from src.data.realtime_evaluator import (
    FeedEvaluationConfig,
    FeedEvaluationResult,
    RealTimeFeedEvaluator,
    ShadowComparisonReport,
)
from src.interfaces.cli.data_manifest import record_manifest

DEFAULT_EVAL_TEMPLATE = Path("reports/performance/feed_evaluation/templates/eval.md")
DEFAULT_EVAL_DIR = Path("reports/performance/feed_evaluation")
DEFAULT_PLOTS_DIR = Path("plots/feed_eval")
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")
DEFAULT_PROVIDER_PRIORITY = Path("config/provider_priority.yaml")
DEFAULT_CANDIDATES_PATH = Path("config/providers/real_time_candidates.yaml")


def plan_feed_eval(
    *,
    provider_id: str,
    window_hours: float,
    symbols: list[str],
    output_dir: Path = DEFAULT_EVAL_DIR,
    runbook_ref: str = "RUN-DATA-07",
) -> Path:
    output_path = _plan_output_path(output_dir, provider_id)
    lines = [
        "# Real-time Feed Evaluation Plan",
        f"- provider: {provider_id}",
        f"- window_hours: {window_hours}",
        f"- symbols: {', '.join(symbols)}",
        f"- runbook_ref: {runbook_ref}",
        "",
        "## Checklist",
        "- [ ] API key provisioned",
        "- [ ] Licensing review complete",
        "- [ ] Ops on-call assigned",
        "- [ ] Cost estimate approved",
        "- [ ] Evaluation scheduled",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _append_ops_worklog(
        {
            "task": "feed_eval.plan",
            "provider_id": provider_id,
            "window_hours": window_hours,
            "plan_path": str(output_path),
        }
    )
    return output_path


def run_feed_eval(
    *,
    provider_id: str,
    window_hours: float,
    fetch_samples_ms: list[float],
    processing_samples_ms: list[float],
    comparison_gap_pips: list[float] | None,
    rate_limit_hits: int,
    uptime_pct: float,
    cost_per_hour_jpy: float | None,
    license_ok: bool,
    output_dir: Path = DEFAULT_EVAL_DIR,
    template_path: Path = DEFAULT_EVAL_TEMPLATE,
    shadow_report: ShadowComparisonReport | None = None,
) -> tuple[FeedEvaluationResult, Path]:
    evaluator = RealTimeFeedEvaluator()
    result = evaluator.run(
        provider_id=provider_id,
        window_hours=window_hours,
        fetch_samples_ms=fetch_samples_ms,
        processing_samples_ms=processing_samples_ms,
        comparison_gap_pips=comparison_gap_pips,
        rate_limit_hits=rate_limit_hits,
        uptime_pct=uptime_pct,
        cost_per_hour_jpy=cost_per_hour_jpy,
        license_ok=license_ok,
    )
    output_path = _result_output_path(output_dir, provider_id)
    rendered = _render_template(template_path, result, shadow_report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    _append_ops_worklog(
        {
            "task": "feed_eval.run",
            "provider_id": provider_id,
            "window_hours": window_hours,
            "result_path": str(output_path),
            "decision": result.decision,
        }
    )
    return result, output_path


def compare_feed_eval(
    *,
    provider_id: str,
    primary_provider: str,
    window_hours: float,
    comparison_gap_pips: list[float],
    missing_pct: float,
    output_dir: Path = DEFAULT_PLOTS_DIR,
) -> Path:
    evaluator = RealTimeFeedEvaluator()
    report = evaluator.shadow_compare(
        provider_id=provider_id,
        primary_provider=primary_provider,
        window_hours=window_hours,
        comparison_gap_pips=comparison_gap_pips,
        missing_pct=missing_pct,
    )
    base_dir = output_dir / provider_id / _timestamp_id()
    base_dir.mkdir(parents=True, exist_ok=True)
    payload_path = base_dir / "comparison.json"
    payload_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_placeholder_plot(base_dir / "gap_p95.png")
    _write_placeholder_plot(base_dir / "missing_pct.png")
    _append_ops_worklog(
        {
            "task": "feed_eval.compare",
            "provider_id": provider_id,
            "primary_provider": primary_provider,
            "window_hours": window_hours,
            "output_dir": str(base_dir),
        }
    )
    return base_dir


def promote_feed_provider(
    *,
    provider_id: str,
    effective_date: str,
    compliance_id: str,
    confirm_cost: bool,
    yes: bool,
    provider_priority_path: Path = DEFAULT_PROVIDER_PRIORITY,
    candidates_path: Path = DEFAULT_CANDIDATES_PATH,
) -> dict[str, object]:
    if not confirm_cost or not yes:
        raise ValueError("promote requires --confirm-cost and --yes")
    if not compliance_id:
        raise ValueError("--compliance-id is required")
    updated = _promote_provider_priority(provider_priority_path, provider_id)
    manifest_entries = [
        record_manifest(path=provider_priority_path, kind="provider_priority", owner="ops"),
    ]
    if candidates_path.exists():
        manifest_entries.append(
            record_manifest(path=candidates_path, kind="provider_candidates", owner="ops")
        )
    _append_ops_worklog(
        {
            "task": "feed_eval.promote",
            "provider_id": provider_id,
            "effective_date": effective_date,
            "compliance_id": compliance_id,
            "provider_priority_path": str(provider_priority_path),
        }
    )
    return {
        "status": "ok",
        "provider_id": provider_id,
        "effective_date": effective_date,
        "provider_priority_path": str(provider_priority_path),
        "updated": updated,
        "manifest_entries": manifest_entries,
    }


def apply_thresholds_for_eval(
    *, result: FeedEvaluationResult, config: FeedEvaluationConfig | None = None
) -> dict[str, object]:
    monitor = HealthMonitor()
    proposal = RealTimeFeedEvaluator(config=config).apply_thresholds(result)
    monitor.raise_condition(
        "warning",
        "feed_eval_threshold_proposal",
        detail=f"provider={proposal.provider_id} max_fetch_p95_ms={proposal.max_fetch_p95_ms}",
        recommended_action="runbook:RUN-DATA-07",
    )
    return proposal.to_dict()


def _render_template(
    template_path: Path, result: FeedEvaluationResult, shadow: ShadowComparisonReport | None
) -> str:
    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
    else:
        template = "\n".join(
            [
                "# Feed Evaluation Report",
                "- provider: {{provider_id}}",
                "- window_hours: {{window_hours}}",
                "- decision: {{decision}}",
                "",
                "## Metrics",
                "- fetch_p95_ms: {{fetch_p95_ms}}",
                "- fetch_p99_ms: {{fetch_p99_ms}}",
                "- processing_p95_ms: {{processing_p95_ms}}",
                "- uptime_pct: {{uptime_pct}}",
                "- rate_limit_hits: {{rate_limit_hits}}",
                "- cost_per_hour_jpy: {{cost_per_hour_jpy}}",
                "- comparison_gap_p95_pips: {{comparison_gap_p95_pips}}",
                "",
                "## Ops Notes",
                "- compliance_sign: [ ]",
            ]
        )
    replacements = {
        "provider_id": result.provider_id,
        "window_hours": result.window_hours,
        "decision": result.decision,
        "fetch_p95_ms": result.fetch_p95_ms,
        "fetch_p99_ms": result.fetch_p99_ms,
        "processing_p95_ms": result.processing_p95_ms,
        "uptime_pct": result.uptime_pct,
        "rate_limit_hits": result.rate_limit_hits,
        "cost_per_hour_jpy": result.cost_per_hour_jpy,
        "comparison_gap_p95_pips": result.comparison_gap_p95_pips,
    }
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    if shadow is not None:
        rendered += "\n\n## Shadow Comparison\n"
        rendered += json.dumps(shadow.to_dict(), ensure_ascii=False, indent=2)
        rendered += "\n"
    return rendered + "\n"


def _promote_provider_priority(path: Path, provider_id: str) -> dict[str, object]:
    if path.exists():
        payload = yaml_safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        payload = {"schema_version": "provider_priority.v1", "default_order": [], "per_symbol": {}}
    default_order = list(payload.get("default_order") or [])
    if provider_id in default_order:
        default_order.remove(provider_id)
    default_order.insert(0, provider_id)
    payload["default_order"] = default_order
    per_symbol = payload.get("per_symbol") or {}
    if isinstance(per_symbol, dict):
        for symbol, providers in per_symbol.items():
            if not isinstance(providers, list):
                continue
            if provider_id in providers:
                providers.remove(provider_id)
            providers.insert(0, provider_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if yaml_safe_dump(path, payload):
        return {"default_order": default_order, "per_symbol": per_symbol}
    path.write_text(
        "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"default_order": default_order, "per_symbol": per_symbol}


def yaml_safe_load(text: str) -> dict[str, object] | None:
    try:
        import yaml
    except Exception:
        return None
    payload = yaml.safe_load(text)
    if isinstance(payload, dict):
        return payload
    return None


def yaml_safe_dump(path: Path, payload: dict[str, object]) -> bool:
    try:
        import yaml
    except Exception:
        return False
    if not hasattr(yaml, "safe_dump"):
        return False
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return True


def _plan_output_path(output_dir: Path, provider_id: str) -> Path:
    date_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    return output_dir / provider_id / f"plan_{date_tag}.md"


def _result_output_path(output_dir: Path, provider_id: str) -> Path:
    date_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return output_dir / provider_id / f"eval_{date_tag}.md"


def _timestamp_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_placeholder_plot(path: Path) -> None:
    path.write_text("PLOT PLACEHOLDER\n", encoding="utf-8")


def _append_ops_worklog(payload: dict[str, object]) -> None:
    DEFAULT_OPS_WORKLOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": _utcnow_iso(), **payload}
    with DEFAULT_OPS_WORKLOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False))
        handle.write("\n")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "plan_feed_eval",
    "run_feed_eval",
    "compare_feed_eval",
    "promote_feed_provider",
    "apply_thresholds_for_eval",
]
