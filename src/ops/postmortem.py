"""Incident postmortem scaffolding for M1.1 ops hardening."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

INCIDENT_REPORT_DIR = Path("reports/ops/incidents")
"""Root directory for incident postmortems."""

INCIDENT_LOG_PATH = Path("logs/ops/incidents.jsonl")
"""JSONL log for incident record changes."""

INCIDENT_TEMPLATE_PATH = Path("docs/templates/postmortem.md")
"""Template used for rendering incident postmortem summaries."""

INCIDENT_AUDIT_DIR = Path("logs/audit")
"""Directory for incident audit logs."""

INCIDENT_METRICS_PATH = Path("metrics/incident_postmortem.jsonl")
"""Metrics log for incident postmortem summaries."""

INCIDENT_PLAYBOOK_PATH = Path("docs/validation_playbook/AC43_postmortem.yaml")
"""Validation playbook log for incident postmortems."""


class IncidentError(Exception):
    """Base exception for incident postmortem service."""


class IncidentNotFoundError(IncidentError):
    """Raised when an incident record cannot be found."""


class IncidentClosureError(IncidentError):
    """Raised when attempting to close an incident with open follow-ups."""


@dataclass(slots=True)
class TimelineEntry:
    ts: datetime
    runbook_ref: str | None
    note: str
    evidence_paths: list[str]
    duration_min: int | None = None


@dataclass(slots=True)
class FollowUpTask:
    task_id: str
    description: str
    owner: str | None
    due: str | None
    status: str = "open"


@dataclass(slots=True)
class IncidentRecord:
    incident_id: str
    category: str
    severity: str
    status: str
    opened_at: datetime
    detected_by: str | None
    board_mode: str
    health_state: str
    related_events: list[str]
    timeline: list[TimelineEntry] = field(default_factory=list)
    follow_ups: list[FollowUpTask] = field(default_factory=list)
    closed_at: datetime | None = None


class IncidentPostmortemService:
    """Persist incident postmortem records and render templates."""

    def __init__(
        self,
        *,
        report_dir: Path = INCIDENT_REPORT_DIR,
        log_path: Path = INCIDENT_LOG_PATH,
        template_path: Path = INCIDENT_TEMPLATE_PATH,
        audit_dir: Path = INCIDENT_AUDIT_DIR,
        metrics_path: Path = INCIDENT_METRICS_PATH,
        validation_playbook_path: Path = INCIDENT_PLAYBOOK_PATH,
    ) -> None:
        self._report_dir = report_dir
        self._log_path = log_path
        self._template_path = template_path
        self._audit_dir = audit_dir
        self._metrics_path = metrics_path
        self._validation_playbook_path = validation_playbook_path

    def open(
        self,
        *,
        category: str,
        severity: str,
        detected_by: str | None = None,
        board_mode: str = "normal",
        health_state: str = "ok",
        related_events: list[str] | None = None,
    ) -> IncidentRecord:
        incident_id = self._generate_incident_id()
        record = IncidentRecord(
            incident_id=incident_id,
            category=category,
            severity=severity,
            status="open",
            opened_at=datetime.now(timezone.utc),
            detected_by=detected_by,
            board_mode=board_mode,
            health_state=health_state,
            related_events=list(related_events or []),
        )
        self._persist_record(record)
        self._write_timeline(record)
        self._render_postmortem(record)
        self._append_audit("audit.incident_opened", record)
        return record

    def append_timeline(
        self,
        *,
        incident_id: str,
        runbook_ref: str | None,
        note: str,
        evidence_paths: list[str] | None = None,
        duration_min: int | None = None,
    ) -> TimelineEntry:
        record = self._load_record(incident_id)
        entry = TimelineEntry(
            ts=datetime.now(timezone.utc),
            runbook_ref=runbook_ref,
            note=note,
            evidence_paths=list(evidence_paths or []),
            duration_min=duration_min,
        )
        record.timeline.append(entry)
        self._persist_record(record)
        self._write_timeline(record)
        self._append_audit("audit.incident_updated", record)
        return entry

    def register_follow_up(
        self,
        *,
        incident_id: str,
        description: str,
        owner: str | None = None,
        due: str | None = None,
        status: str = "open",
    ) -> FollowUpTask:
        record = self._load_record(incident_id)
        task = FollowUpTask(
            task_id=f"{incident_id}-FU-{len(record.follow_ups) + 1:02d}",
            description=description,
            owner=owner,
            due=due,
            status=status,
        )
        record.follow_ups.append(task)
        self._persist_record(record)
        self._render_postmortem(record)
        self._append_audit("audit.incident_updated", record)
        return task

    def update_follow_up_status(
        self,
        *,
        incident_id: str,
        task_id: str,
        status: str,
    ) -> FollowUpTask:
        record = self._load_record(incident_id)
        for task in record.follow_ups:
            if task.task_id == task_id:
                task.status = status
                self._persist_record(record)
                self._render_postmortem(record)
                self._append_audit("audit.incident_updated", record)
                return task
        raise IncidentNotFoundError(f"{incident_id}:{task_id}")

    def close(
        self,
        *,
        incident_id: str,
        verification_note: str,
        verified_by: str,
    ) -> IncidentRecord:
        record = self._load_record(incident_id)
        open_tasks = [task for task in record.follow_ups if task.status not in {"done", "closed"}]
        if open_tasks:
            raise IncidentClosureError("follow-up tasks remain open")
        record.status = "closed"
        record.closed_at = datetime.now(timezone.utc)
        self._persist_record(record)
        self._render_postmortem(record, verification_note=verification_note, verified_by=verified_by)
        self._append_metrics(record)
        self._append_validation_playbook(record)
        self._append_audit("audit.incident_closed", record)
        return record

    def _generate_incident_id(self) -> str:
        date_stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        existing = sorted(self._report_dir.glob(f"INC-{date_stamp}-*"))
        sequence = len(existing) + 1
        return f"INC-{date_stamp}-{sequence:02d}"

    def _persist_record(self, record: IncidentRecord) -> None:
        incident_dir = self._report_dir / record.incident_id
        incident_dir.mkdir(parents=True, exist_ok=True)
        record_path = incident_dir / "incident.json"
        record_path.write_text(json.dumps(_record_to_dict(record), ensure_ascii=False, indent=2), encoding="utf-8")
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_record_to_dict(record), ensure_ascii=False))
            handle.write("\n")

    def _load_record(self, incident_id: str) -> IncidentRecord:
        record_path = self._report_dir / incident_id / "incident.json"
        if not record_path.exists():
            raise IncidentNotFoundError(incident_id)
        payload = json.loads(record_path.read_text(encoding="utf-8"))
        return _record_from_dict(payload)

    def get_record(self, incident_id: str) -> IncidentRecord:
        """Return a parsed incident record."""

        return self._load_record(incident_id)

    def _render_postmortem(
        self,
        record: IncidentRecord,
        *,
        verification_note: str | None = None,
        verified_by: str | None = None,
    ) -> Path:
        if not self._template_path.exists():
            raise FileNotFoundError(self._template_path)
        template = self._template_path.read_text(encoding="utf-8")
        context = {
            "incident_id": record.incident_id,
            "category": record.category,
            "severity": record.severity,
            "status": record.status,
            "opened_at": record.opened_at.isoformat().replace("+00:00", "Z"),
            "closed_at": record.closed_at.isoformat().replace("+00:00", "Z") if record.closed_at else "n/a",
            "board_mode": record.board_mode,
            "health_state": record.health_state,
            "verification_note": verification_note or "n/a",
            "verified_by": verified_by or "n/a",
        }
        sections = {
            "timeline": [
                {
                    "ts": entry.ts.isoformat().replace("+00:00", "Z"),
                    "runbook_ref": entry.runbook_ref or "n/a",
                    "note": entry.note,
                    "evidence": ", ".join(entry.evidence_paths) if entry.evidence_paths else "n/a",
                }
                for entry in record.timeline
            ],
            "follow_ups": [
                {
                    "task_id": task.task_id,
                    "description": task.description,
                    "owner": task.owner or "n/a",
                    "due": task.due or "n/a",
                    "status": task.status,
                }
                for task in record.follow_ups
            ],
        }
        rendered = _render_template(template, context=context, sections=sections)
        output_path = self._report_dir / record.incident_id / "postmortem.md"
        output_path.write_text(rendered, encoding="utf-8")
        return output_path

    def _write_timeline(self, record: IncidentRecord) -> None:
        output_path = self._report_dir / record.incident_id / "timeline.md"
        lines = [
            "# Incident Timeline",
            "",
            "| Timestamp | Runbook | Note | Evidence | Duration (min) |",
            "| --- | --- | --- | --- | --- |",
        ]
        if record.timeline:
            for entry in record.timeline:
                evidence = ", ".join(entry.evidence_paths) if entry.evidence_paths else "n/a"
                lines.append(
                    f"| {entry.ts.isoformat().replace('+00:00', 'Z')} | {entry.runbook_ref or 'n/a'} | {entry.note} | {evidence} | {entry.duration_min or 'n/a'} |"
                )
        else:
            lines.append("| n/a | n/a | n/a | n/a | n/a |")
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _append_audit(self, event: str, record: IncidentRecord) -> None:
        payload = {
            "event": event,
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "incident_id": record.incident_id,
            "status": record.status,
            "board_mode": record.board_mode,
        }
        self._audit_dir.mkdir(parents=True, exist_ok=True)
        audit_path = self._audit_dir / f"ops_incidents_{datetime.now(timezone.utc):%Y%m%d}.jsonl"
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _append_metrics(self, record: IncidentRecord) -> None:
        if record.closed_at is None:
            return
        time_to_detect_min = None
        time_to_contain_min = None
        if record.timeline:
            timeline_ts = [entry.ts for entry in record.timeline]
            first_ts = min(timeline_ts)
            last_ts = max(timeline_ts)
            time_to_detect_min = max(
                0.0, round((first_ts - record.opened_at).total_seconds() / 60.0, 2)
            )
            time_to_contain_min = max(
                0.0, round((last_ts - record.opened_at).total_seconds() / 60.0, 2)
            )
        time_to_close_hr = (record.closed_at - record.opened_at).total_seconds() / 3600.0
        payload = {
            "incident_id": record.incident_id,
            "severity": record.severity,
            "time_to_detect_min": time_to_detect_min,
            "time_to_contain_min": time_to_contain_min,
            "time_to_close_hr": round(time_to_close_hr, 2),
            "follow_ups_open": len(
                [task for task in record.follow_ups if task.status not in {"done", "closed"}]
            ),
        }
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _append_validation_playbook(self, record: IncidentRecord) -> None:
        postmortem_path = self._report_dir / record.incident_id / "postmortem.md"
        postmortem_hash = None
        if postmortem_path.exists():
            import hashlib

            digest = hashlib.sha256(postmortem_path.read_bytes()).hexdigest()
            postmortem_hash = f"sha256:{digest}"
        entry = {
            "incident_id": record.incident_id,
            "postmortem_path": str(postmortem_path),
            "postmortem_hash": postmortem_hash,
            "closed_at": record.closed_at.isoformat().replace("+00:00", "Z")
            if record.closed_at
            else None,
        }
        self._validation_playbook_path.parent.mkdir(parents=True, exist_ok=True)
        if self._validation_playbook_path.exists():
            lines = self._validation_playbook_path.read_text(encoding="utf-8").splitlines()
            if not lines:
                lines = [
                    "validation_playbook_id: AC43_postmortem",
                    "category: incident_postmortem",
                    "entries:",
                ]
        else:
            lines = [
                "validation_playbook_id: AC43_postmortem",
                "category: incident_postmortem",
                "entries:",
            ]
        lines.append(
            f"  - incident_id: {entry['incident_id']}"
        )
        lines.append(f"    postmortem_path: {entry['postmortem_path']}")
        lines.append(f"    postmortem_hash: {entry['postmortem_hash']}")
        lines.append("    runbook_ref: RUN-INC-01")
        lines.append(f"    closed_at: {entry['closed_at']}")
        self._validation_playbook_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _render_template(
    template: str,
    *,
    context: dict[str, object],
    sections: dict[str, list[dict[str, object]]],
) -> str:
    rendered = template
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    rendered = _render_section(rendered, "timeline", sections.get("timeline", []), ["ts", "runbook_ref", "note", "evidence"])
    rendered = _render_section(
        rendered,
        "follow_ups",
        sections.get("follow_ups", []),
        ["task_id", "description", "owner", "due", "status"],
    )
    return rendered


def _render_section(
    template: str,
    section: str,
    rows: list[dict[str, object]],
    columns: list[str],
) -> str:
    start_tag = f"{{#{section}}}"
    end_tag = f"{{/{section}}}"
    if start_tag not in template or end_tag not in template:
        return template
    start_index = template.index(start_tag)
    end_index = template.index(end_tag)
    row_template = template[start_index + len(start_tag) : end_index]
    if rows:
        rendered_rows = []
        for row in rows:
            line = row_template
            for col in columns:
                line = line.replace(f"{{{{{col}}}}}", str(row.get(col, "n/a")))
            rendered_rows.append(line)
        rendered_block = "".join(rendered_rows)
    else:
        line = row_template
        for col in columns:
            line = line.replace(f"{{{{{col}}}}}", "n/a")
        rendered_block = line
    return template[:start_index] + rendered_block + template[end_index + len(end_tag) :]


def _record_to_dict(record: IncidentRecord) -> dict[str, object]:
    return {
        "incident_id": record.incident_id,
        "category": record.category,
        "severity": record.severity,
        "status": record.status,
        "opened_at": record.opened_at.isoformat().replace("+00:00", "Z"),
        "detected_by": record.detected_by,
        "board_mode": record.board_mode,
        "health_state": record.health_state,
        "related_events": list(record.related_events),
        "timeline": [
            {
                "ts": entry.ts.isoformat().replace("+00:00", "Z"),
                "runbook_ref": entry.runbook_ref,
                "note": entry.note,
                "evidence_paths": list(entry.evidence_paths),
                "duration_min": entry.duration_min,
            }
            for entry in record.timeline
        ],
        "follow_ups": [
            {
                "task_id": task.task_id,
                "description": task.description,
                "owner": task.owner,
                "due": task.due,
                "status": task.status,
            }
            for task in record.follow_ups
        ],
        "closed_at": record.closed_at.isoformat().replace("+00:00", "Z") if record.closed_at else None,
    }


def _record_from_dict(payload: dict[str, object]) -> IncidentRecord:
    opened_at = datetime.fromisoformat(str(payload.get("opened_at")).replace("Z", "+00:00"))
    closed_raw = payload.get("closed_at")
    closed_at = (
        datetime.fromisoformat(str(closed_raw).replace("Z", "+00:00")) if closed_raw else None
    )
    timeline_entries = []
    for entry in payload.get("timeline", []) or []:
        ts = datetime.fromisoformat(str(entry.get("ts")).replace("Z", "+00:00"))
        timeline_entries.append(
            TimelineEntry(
                ts=ts,
                runbook_ref=entry.get("runbook_ref"),
                note=str(entry.get("note", "")),
                evidence_paths=list(entry.get("evidence_paths", [])),
                duration_min=entry.get("duration_min"),
            )
        )
    follow_ups = []
    for item in payload.get("follow_ups", []) or []:
        follow_ups.append(
            FollowUpTask(
                task_id=str(item.get("task_id", "")),
                description=str(item.get("description", "")),
                owner=item.get("owner"),
                due=item.get("due"),
                status=str(item.get("status", "open")),
            )
        )
    return IncidentRecord(
        incident_id=str(payload.get("incident_id", "")),
        category=str(payload.get("category", "")),
        severity=str(payload.get("severity", "")),
        status=str(payload.get("status", "")),
        opened_at=opened_at,
        detected_by=payload.get("detected_by"),
        board_mode=str(payload.get("board_mode", "")),
        health_state=str(payload.get("health_state", "")),
        related_events=list(payload.get("related_events", [])),
        timeline=timeline_entries,
        follow_ups=follow_ups,
        closed_at=closed_at,
    )


__all__ = [
    "INCIDENT_REPORT_DIR",
    "INCIDENT_LOG_PATH",
    "INCIDENT_TEMPLATE_PATH",
    "INCIDENT_AUDIT_DIR",
    "INCIDENT_METRICS_PATH",
    "INCIDENT_PLAYBOOK_PATH",
    "IncidentError",
    "IncidentNotFoundError",
    "IncidentClosureError",
    "TimelineEntry",
    "FollowUpTask",
    "IncidentRecord",
    "IncidentPostmortemService",
]
