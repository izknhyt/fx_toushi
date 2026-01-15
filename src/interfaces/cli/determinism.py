"""CLI helpers for determinism replay diagnostics."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.replay_signals import diff_signals

from src.audit.trace import trace_order
from src.interfaces.cli.diagnostics import DEFAULT_DETERMINISM_LOG, load_determinism_events

__all__ = ["DeterminismReplayRequest", "determinism_replay"]


@dataclass(slots=True)
class DeterminismReplayRequest:
    """Request payload describing a determinism replay job."""

    since: str
    until: str | None
    mode: str
    strategy: str | None
    window: str | None
    output: Path | None
    log_path: Path
    signals_path: Path | None = None

    def to_record(self, *, job_id: str) -> Mapping[str, Any]:
        record = asdict(self)
        record["log_path"] = str(self.log_path)
        if self.signals_path:
            record["signals_path"] = str(self.signals_path)
        record["job_id"] = job_id
        record["requested_at"] = datetime.utcnow().isoformat() + "Z"
        return record


def determinism_replay(
    *,
    since: str,
    until: str | None,
    mode: str,
    strategy: str | None,
    window: str | None,
    output: Path | None,
    log_path: Path | None = None,
    metrics_path: Path | None = None,
    signals_expected: Path | None = None,
    signals_actual: Path | None = None,
    allow_missing_signals: bool = False,
    allow_diff: bool = False,
    allow_signals_invalid: bool = False,
    signals_schema: Path | None = None,
) -> Mapping[str, Any]:
    """Return a summary payload for a determinism replay request."""

    job_id = f"replay-{uuid.uuid4().hex[:8]}"
    resolved_log = log_path or DEFAULT_DETERMINISM_LOG
    report_root = Path("reports") / "determinism" / datetime.utcnow().strftime("%Y%m%d")
    request = DeterminismReplayRequest(
        since=since,
        until=until,
        mode=mode,
        strategy=strategy,
        window=window,
        output=output,
        log_path=resolved_log,
        signals_path=signals_expected,
    )
    events_payload: Mapping[str, Any] | None = None
    filtered_events: list[Mapping[str, Any]] = []
    try:
        events_payload = load_determinism_events(resolved_log)
        filtered_events = _filter_events(
            events_payload.get("events", ()), strategy=strategy, since=since, until=until
        )
    except Exception:
        events_payload = None
        filtered_events = []

    diff_count = _compute_diff_count(filtered_events)
    signals_summary = None
    signals_markdown = None
    signals_diffs: list[Mapping[str, Any]] | None = None
    if signals_expected or signals_actual:
        if not (signals_expected and signals_actual) and not allow_missing_signals:
            raise FileNotFoundError("Both --signals-expected and --signals-actual are required")
        default_schema = Path("docs") / "schemas" / "signal_record.schema.json"
        schema_to_use = signals_schema if signals_schema is not None else default_schema
        if schema_to_use and not schema_to_use.exists() and not allow_signals_invalid:
            raise FileNotFoundError(f"Signals schema not found: {schema_to_use}")
        if (
            signals_expected
            and signals_actual
            and signals_expected.exists()
            and signals_actual.exists()
        ):
            signal_diff = diff_signals(
                signals_expected,
                signals_actual,
                allow_invalid=allow_signals_invalid,
                schema_path=schema_to_use,
            )
            signals_summary = signal_diff.get("summary")
            signals_markdown = signal_diff.get("markdown_table")
            signals_diffs = list(signal_diff.get("diffs") or [])

    summary = {
        "event_count": len(filtered_events),
        "strategy_count": len(
            {evt.get("strategy_id") for evt in filtered_events if "strategy_id" in evt}
        ),
        "diff_count": diff_count,
        "log_path": str(resolved_log),
        "signals": signals_summary,
    }
    report_paths: list[str] = []
    diff_artifacts: dict[str, str] = {}
    if filtered_events:
        report_paths = _write_reports(
            events=filtered_events,
            root=report_root,
            strategy_filter=strategy,
            job_id=job_id,
            signals=signals_summary,
            signals_markdown=signals_markdown,
        )
    if signals_diffs is not None:
        diff_artifacts = _write_signal_diff_artifacts(
            root=report_root,
            strategy=strategy,
            job_id=job_id,
            summary=signals_summary,
            diffs=signals_diffs,
            markdown_table=signals_markdown,
        )

    payload = {
        "job": request.to_record(job_id=job_id),
        "summary": summary,
        "status": "ok" if events_payload is not None else "log_missing",
        "diagnostics": events_payload,
        "output": str(output) if output else None,
        "reports": report_paths,
        "signals_summary": signals_summary,
        "diff_report": diff_artifacts.get("diff_report"),
        "diffs_path": diff_artifacts.get("diffs_path"),
    }
    _emit_audit_replay(payload)
    _append_validation_log(payload)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        serialisable = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
        output.write_text(json.dumps(serialisable, ensure_ascii=False, indent=2), encoding="utf-8")

    resolved_metrics = metrics_path or Path("metrics") / "replay_jobs.jsonl"
    try:
        resolved_metrics.parent.mkdir(parents=True, exist_ok=True)
        seed = next(
            (
                evt.get("seed")
                for evt in filtered_events
                if isinstance(evt.get("seed"), (int, float))
            ),
            None,
        )
        max_latency_ms = _max_latency_ms(signals_diffs)
        metric_record = {
            "event": "determinism.replay",
            "job_id": job_id,
            "mode": mode,
            "strategy": strategy,
            "since": since,
            "until": until,
            "window": window,
            "event_count": summary["event_count"],
            "diff_count": summary["diff_count"],
            "max_latency_ms": max_latency_ms,
            "seed": seed,
            "status": payload["status"],
            "log_path": str(resolved_log),
            "ts": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "signals_expected": str(signals_expected) if signals_expected else None,
            "signals_actual": str(signals_actual) if signals_actual else None,
            "signals_diff_count": signals_summary["diff_count"] if signals_summary else None,
        }
        with resolved_metrics.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metric_record, ensure_ascii=False))
            handle.write("\n")
        payload["metrics_path"] = str(resolved_metrics)
    except OSError:
        payload["metrics_path"] = None

    return payload


def _should_exit(
    signals_expected: Path | None,
    signals_actual: Path | None,
    allow_missing: bool,
    allow_diff: bool,
    diff_count: int,
) -> int | None:
    if (signals_expected and not signals_expected.exists()) or (
        signals_actual and not signals_actual.exists()
    ):
        return None if allow_missing else 75
    if diff_count > 0 and not allow_diff:
        return 76
    return None


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except Exception:
            return None
    text = str(value)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _filter_events(
    events: list[Mapping[str, Any]] | Any, *, strategy: str | None, since: str, until: str | None
) -> list[Mapping[str, Any]]:
    parsed_events: list[Mapping[str, Any]] = []
    start_ts = _parse_ts(since)
    end_ts = _parse_ts(until) if until else None
    for event in events or []:
        if strategy and event.get("strategy_id") != strategy:
            continue
        ts = _parse_ts(event.get("ts"))
        if start_ts and ts and ts < start_ts:
            continue
        if end_ts and ts and ts > end_ts:
            continue
        parsed_events.append(event)
    return parsed_events


def _compute_diff_count(events: list[Mapping[str, Any]]) -> int:
    per_strategy: dict[str, set[str]] = {}
    for event in events:
        strategy_id = str(event.get("strategy_id") or "unknown")
        hash_value = event.get("determinism_hash") or event.get("deterministic_hash")
        if hash_value:
            per_strategy.setdefault(strategy_id, set()).add(str(hash_value))
    return sum(max(0, len(hashes) - 1) for hashes in per_strategy.values())


def _load_jsonl(path: Path) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                records.append(json.loads(text))
            except json.JSONDecodeError:
                continue
    return records


def _summarise_signals(records: list[Mapping[str, Any]]) -> Mapping[str, Any]:
    if not records:
        return {"count": 0, "hash": None}
    digest = hashlib.blake2b(
        json.dumps(records, sort_keys=True, default=str).encode("utf-8"), digest_size=16
    ).hexdigest()
    return {"count": len(records), "hash": digest}


def _emit_audit_replay(payload: Mapping[str, Any]) -> None:
    try:
        trace_order(
            "audit.determinism_replay",
            payload={
                "job_id": payload.get("job", {}).get("job_id"),
                "status": payload.get("status"),
                "summary": payload.get("summary"),
                "reports": payload.get("reports"),
                "signals": payload.get("signals_summary"),
                "ts": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            },
        )
    except Exception:
        return


def _append_validation_log(payload: Mapping[str, Any]) -> None:
    try:
        job = payload.get("job", {})
        summary = payload.get("summary", {})
        signals = summary.get("signals")
        expected_count = signals.get("expected_count") if signals else "n/a"
        actual_count = signals.get("actual_count") if signals else "n/a"
        diff_count = signals.get("diff_count") if signals else "n/a"
        date_stamp = datetime.utcnow().strftime("%Y%m%d")
        log_path = Path("reports") / "validation_log" / f"AC-07_determinism_{date_stamp}.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        signals_line = (
            f"| Signals (expected/actual/diff) | {expected_count} / "
            f"{actual_count} / {diff_count} |"
        )
        lines = [
            f"## Determinism Replay {job.get('job_id')}",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Status | {payload.get('status')} |",
            f"| Mode | {job.get('mode')} |",
            f"| Strategy | {job.get('strategy')} |",
            f"| Since → Until | {job.get('since')} → {job.get('until')} |",
            f"| Events | {summary.get('event_count')} |",
            f"| Diff Count | {summary.get('diff_count')} |",
            signals_line,
            f"| Reports | {', '.join(payload.get('reports') or [])} |",
            "| Runbook | docs/runbooks/RUN-DET-01.md |",
            "",
        ]
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
    except Exception:
        return


def _write_reports(
    *,
    events: list[Mapping[str, Any]],
    root: Path,
    strategy_filter: str | None,
    job_id: str,
    signals: Mapping[str, Any] | None,
    signals_markdown: str | None = None,
) -> list[str]:
    """Persist JSON/Markdown reports summarising determinism diff counts."""

    root.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for event in events:
        sid = event.get("strategy_id") or "unknown"
        if strategy_filter and sid != strategy_filter:
            continue
        grouped.setdefault(sid, []).append(event)

    written: list[str] = []
    for strategy_id, strategy_events in grouped.items():
        strategy_dir = root / strategy_id
        strategy_dir.mkdir(parents=True, exist_ok=True)
        json_path = strategy_dir / f"{job_id}.json"
        md_path = strategy_dir / f"{job_id}.md"

        summary = {
            "job_id": job_id,
            "strategy_id": strategy_id,
            "event_count": len(strategy_events),
            "hashes": sorted(
                {
                    evt.get("determinism_hash") or evt.get("deterministic_hash")
                    for evt in strategy_events
                }
            ),
            "first_ts": strategy_events[0].get("ts"),
            "last_ts": strategy_events[-1].get("ts"),
            "signals": signals,
            "signals_markdown": signals_markdown,
        }
        json_payload = {
            "summary": summary,
            "events": strategy_events,
            "signals_markdown": signals_markdown,
        }
        json_path.write_text(
            json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        hashes = summary["hashes"]
        md_lines = [
            f"# Determinism Replay Report ({strategy_id})",
            "",
            f"- Job: `{job_id}`",
            f"- Events: {summary['event_count']}",
            f"- Hashes: {', '.join(str(h) for h in hashes if h)}",
            f"- Window: {summary['first_ts']} → {summary['last_ts']}",
        ]
        if signals_markdown:
            md_lines.append("\n## Signals Diff\n")
            md_lines.append(signals_markdown)
        md_path.write_text("\n".join(md_lines), encoding="utf-8")

        written.extend([str(json_path), str(md_path)])

    return written


def _write_signal_diff_artifacts(
    *,
    root: Path,
    strategy: str | None,
    job_id: str,
    summary: Mapping[str, Any] | None,
    diffs: list[Mapping[str, Any]],
    markdown_table: str | None,
) -> dict[str, str]:
    if summary is None:
        return {}
    if not diffs and not summary.get("diff_count"):
        return {}
    strategy_id = strategy or "unknown"
    root.mkdir(parents=True, exist_ok=True)
    strategy_dir = root / strategy_id
    strategy_dir.mkdir(parents=True, exist_ok=True)
    diffs_path = strategy_dir / f"diffs_{strategy_id}.json"
    diff_report = root / f"{strategy_id}.md"

    diff_payload = {
        "job_id": job_id,
        "strategy_id": strategy_id,
        "summary": summary,
        "diffs": diffs,
    }
    diffs_path.write_text(
        json.dumps(diff_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        f"# Determinism Diff Report ({strategy_id})",
        "",
        f"- Job: `{job_id}`",
        f"- Generated: {datetime.utcnow().isoformat()}Z",
        f"- Diff Count: {summary.get('diff_count')}",
        f"- Expected Count: {summary.get('expected_count')}",
        f"- Actual Count: {summary.get('actual_count')}",
        f"- Expected Hash: {summary.get('expected_hash')}",
        f"- Actual Hash: {summary.get('actual_hash')}",
    ]
    if markdown_table:
        lines.extend(["", "## Diffs", "", markdown_table])
    diff_report.write_text("\n".join(lines), encoding="utf-8")

    return {"diffs_path": str(diffs_path), "diff_report": str(diff_report)}


def _max_latency_ms(diffs: list[Mapping[str, Any]] | None) -> float | None:
    if not diffs:
        return None
    max_latency: float | None = None
    for diff in diffs:
        for side in ("expected", "actual"):
            payload = diff.get(side)
            if not isinstance(payload, Mapping):
                continue
            latency = payload.get("latency_ms")
            if isinstance(latency, (int, float)):
                value = float(latency)
                if max_latency is None or value > max_latency:
                    max_latency = value
    return max_latency
