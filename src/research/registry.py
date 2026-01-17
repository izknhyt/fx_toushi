"""Idea registry and research manifest helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

DEFAULT_IDEA_ROOT = Path("research") / "ideas"
DEFAULT_EVENT_LOG = Path("logs") / "events" / "research_idea.jsonl"
DEFAULT_REPORT_DIR = Path("reports") / "research" / "ideas"

STAGE_ORDER = ("draft", "screening", "paper", "ready")
DEFAULT_STAGE_REQUIREMENTS = {
    "draft": ("hypothesis",),
    "screening": ("data_sources", "baseline_metrics"),
    "paper": ("validation_report", "risk_review"),
    "ready": ("ops_signoff",),
}


class IdeaRegistryError(RuntimeError):
    """Base error for idea registry issues."""


class IdeaNotFoundError(IdeaRegistryError):
    """Raised when an idea manifest cannot be located."""


class StageTransitionError(IdeaRegistryError):
    """Raised when an invalid stage transition is requested."""


class StageIncompleteError(IdeaRegistryError):
    """Raised when stage checklist requirements are not met."""

    def __init__(self, idea_id: str, missing: Iterable[str]) -> None:
        self.idea_id = idea_id
        self.missing = tuple(missing)
        super().__init__(f"Checklist incomplete for {idea_id}: {', '.join(self.missing)}")


@dataclass(slots=True)
class StageChecklist:
    stage: str
    required_evidence: list[str]
    completed: list[str] = field(default_factory=list)
    signoff: str | None = None
    artifacts: list[str] = field(default_factory=list)

    def missing(self) -> list[str]:
        completed = {item.strip() for item in self.completed if str(item).strip()}
        return [item for item in self.required_evidence if item not in completed]

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "required_evidence": list(self.required_evidence),
            "completed": list(self.completed),
            "signoff": self.signoff,
            "artifacts": list(self.artifacts),
            "missing": self.missing(),
        }


@dataclass(slots=True)
class IdeaRecord:
    idea_id: str
    title: str
    owner: str | None
    created_at: datetime
    hypothesis: str | None
    data_sources: list[str]
    risk_flags: list[str]
    stage: str
    next_actions: list[str]
    reviewers: list[str]
    tags: list[str]
    manifest_path: Path

    def to_dict(self) -> dict[str, object]:
        return {
            "idea_id": self.idea_id,
            "title": self.title,
            "owner": self.owner,
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "hypothesis": self.hypothesis,
            "data_sources": list(self.data_sources),
            "risk_flags": list(self.risk_flags),
            "stage": self.stage,
            "next_actions": list(self.next_actions),
            "reviewers": list(self.reviewers),
            "tags": list(self.tags),
            "manifest_path": str(self.manifest_path),
        }


@dataclass(slots=True)
class StageChange:
    ts: str
    from_stage: str
    to_stage: str
    actor: str | None
    note: str | None
    force: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "ts": self.ts,
            "from": self.from_stage,
            "to": self.to_stage,
            "actor": self.actor,
            "note": self.note,
            "force": self.force,
        }


class IdeaRegistry:
    """Registry for research idea manifests."""

    def __init__(self, root: Path = DEFAULT_IDEA_ROOT) -> None:
        self._root = root

    def list(
        self, *, stage: str | None = None, owner: str | None = None
    ) -> list[IdeaRecord]:
        records = self._load_all()
        if stage:
            records = [record for record in records if record.stage == stage]
        if owner:
            records = [record for record in records if record.owner == owner]
        return records

    def get(self, idea_id: str) -> IdeaRecord:
        manifest_path = self._resolve_manifest(idea_id)
        payload = _load_yaml(manifest_path)
        return _parse_idea_record(payload, manifest_path)

    def checklist(self, idea_id: str, *, stage: str | None = None) -> StageChecklist:
        record = self.get(idea_id)
        target_stage = stage or record.stage
        payload = _load_yaml(record.manifest_path)
        return _parse_checklist(payload, stage=target_stage)

    def advance_stage(
        self,
        idea_id: str,
        *,
        target_stage: str,
        note: str | None = None,
        actor: str | None = None,
        force: bool = False,
        event_log: Path = DEFAULT_EVENT_LOG,
    ) -> StageChecklist:
        record = self.get(idea_id)
        _validate_stage(target_stage)
        current_index = STAGE_ORDER.index(record.stage)
        target_index = STAGE_ORDER.index(target_stage)
        if target_index < current_index and not force:
            raise StageTransitionError(
                f"Cannot regress stage from {record.stage} to {target_stage} without --force"
            )
        checklist = self.checklist(idea_id, stage=target_stage)
        missing = checklist.missing()
        if missing and not force:
            raise StageIncompleteError(idea_id, missing)

        payload = _load_yaml(record.manifest_path)
        payload["stage"] = target_stage
        history = payload.get("stage_history") if isinstance(payload, dict) else None
        parsed_history = _parse_stage_history(history)
        parsed_history.append(
            StageChange(
                ts=_utcnow_iso(),
                from_stage=record.stage,
                to_stage=target_stage,
                actor=actor,
                note=note,
                force=force,
            )
        )
        payload["stage_history"] = [entry.to_dict() for entry in parsed_history]
        _write_yaml(record.manifest_path, payload)
        _append_event(
            event_log,
            {
                "event": "research.idea.stage_changed",
                "ts": _utcnow_iso(),
                "idea_id": idea_id,
                "from": record.stage,
                "to": target_stage,
                "actor": actor,
                "note": note,
                "force": force,
                "manifest_path": str(record.manifest_path),
            },
        )
        return checklist

    def generate_report(
        self,
        idea_id: str,
        *,
        output_dir: Path = DEFAULT_REPORT_DIR,
    ) -> Path:
        record = self.get(idea_id)
        checklist = self.checklist(idea_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{idea_id}.md"
        lines = [
            f"# Idea Report: {record.idea_id}",
            "",
            f"- Title: {record.title}",
            f"- Owner: {record.owner or 'n/a'}",
            f"- Stage: {record.stage}",
            f"- Created: {record.created_at.date().isoformat()}",
            "",
            "## Checklist",
            "",
            "| Item | Status |",
            "| --- | --- |",
        ]
        missing = set(checklist.missing())
        for item in checklist.required_evidence:
            status = "missing" if item in missing else "ok"
            lines.append(f"| {item} | {status} |")
        if record.next_actions:
            lines.append("")
            lines.append("## Next Actions")
            lines.extend([f"- {action}" for action in record.next_actions])
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def _load_all(self) -> list[IdeaRecord]:
        manifests = sorted(self._root.glob("*/manifest.yaml"))
        records: list[IdeaRecord] = []
        for manifest_path in manifests:
            payload = _load_yaml(manifest_path)
            records.append(_parse_idea_record(payload, manifest_path))
        return records

    def _resolve_manifest(self, idea_id: str) -> Path:
        candidate = self._root / idea_id / "manifest.yaml"
        if not candidate.exists():
            raise IdeaNotFoundError(f"Idea manifest not found: {candidate}")
        return candidate


def _parse_idea_record(payload: Mapping[str, Any], path: Path) -> IdeaRecord:
    idea_id = str(payload.get("idea_id") or path.parent.name)
    title = str(payload.get("title") or idea_id)
    owner = payload.get("owner")
    created_at = _parse_datetime(payload.get("created_at")) or datetime.now(timezone.utc)
    hypothesis = payload.get("hypothesis")
    data_sources = _as_list(payload.get("data_sources"))
    risk_flags = _as_list(payload.get("risk_flags"))
    stage = str(payload.get("stage") or "draft")
    _validate_stage(stage)
    next_actions = _as_list(payload.get("next_actions"))
    reviewers = _as_list(payload.get("reviewers"))
    tags = _as_list(payload.get("tags"))
    return IdeaRecord(
        idea_id=idea_id,
        title=title,
        owner=str(owner) if owner else None,
        created_at=created_at,
        hypothesis=str(hypothesis) if hypothesis else None,
        data_sources=data_sources,
        risk_flags=risk_flags,
        stage=stage,
        next_actions=next_actions,
        reviewers=reviewers,
        tags=tags,
        manifest_path=path,
    )


def _parse_checklist(payload: Mapping[str, Any], *, stage: str) -> StageChecklist:
    _validate_stage(stage)
    required = list(DEFAULT_STAGE_REQUIREMENTS.get(stage, ()))
    checklists = payload.get("checklists") or {}
    entry = checklists.get(stage) if isinstance(checklists, Mapping) else {}
    completed = _as_list(entry.get("completed"))
    signoff = entry.get("signoff") if isinstance(entry, Mapping) else None
    artifacts = _as_list(entry.get("artifacts"))
    return StageChecklist(
        stage=stage,
        required_evidence=required,
        completed=completed,
        signoff=str(signoff) if signoff else None,
        artifacts=artifacts,
    )


def _parse_stage_history(history: Any) -> list[StageChange]:
    if not isinstance(history, list):
        return []
    parsed: list[StageChange] = []
    for entry in history:
        if not isinstance(entry, Mapping):
            continue
        parsed.append(
            StageChange(
                ts=str(entry.get("ts") or _utcnow_iso()),
                from_stage=str(entry.get("from") or ""),
                to_stage=str(entry.get("to") or ""),
                actor=str(entry.get("actor")) if entry.get("actor") else None,
                note=str(entry.get("note")) if entry.get("note") else None,
                force=bool(entry.get("force", False)),
            )
        )
    return parsed


def _validate_stage(stage: str) -> None:
    if stage not in STAGE_ORDER:
        raise StageTransitionError(f"Unknown stage '{stage}' (expected {STAGE_ORDER})")


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _load_yaml(path: Path) -> Mapping[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # pragma: no cover - defensive
        raise IdeaRegistryError(f"Failed to parse {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise IdeaRegistryError(f"Invalid idea manifest payload: {path}")
    return payload


def _write_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_yaml(payload), encoding="utf-8")


def _append_event(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_yaml(payload: Mapping[str, Any]) -> str:
    dumper = getattr(yaml, "safe_dump", None)
    if dumper:
        return dumper(payload, sort_keys=False)
    return "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2)


__all__ = [
    "IdeaRegistry",
    "IdeaRecord",
    "StageChecklist",
    "IdeaRegistryError",
    "IdeaNotFoundError",
    "StageTransitionError",
    "StageIncompleteError",
]
