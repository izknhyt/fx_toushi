"""Strategy board service for governance meetings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from src.governance.secure_share import SecureShareService

DEFAULT_BOARD_DIR = Path("reports/governance/strategy_board")
DEFAULT_TEMPLATE = DEFAULT_BOARD_DIR / "templates" / "agenda.md"
DEFAULT_AUDIT_LOG = Path("logs/audit/strategy_board.jsonl")
DEFAULT_DECISIONS_DIR = DEFAULT_BOARD_DIR / "decisions"


@dataclass(slots=True)
class BoardDecision:
    meeting_id: str
    strategy_id: str
    decision: str
    actor: str
    notes: str | None
    recorded_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "meeting_id": self.meeting_id,
            "strategy_id": self.strategy_id,
            "decision": self.decision,
            "actor": self.actor,
            "notes": self.notes,
            "recorded_at": self.recorded_at,
        }


class StrategyBoardService:
    """Service responsible for agenda generation and decision recording."""

    def __init__(
        self,
        *,
        output_dir: Path = DEFAULT_BOARD_DIR,
        template_path: Path = DEFAULT_TEMPLATE,
        audit_log: Path = DEFAULT_AUDIT_LOG,
        decisions_dir: Path | None = None,
    ) -> None:
        self._output_dir = output_dir
        self._template_path = template_path
        self._audit_log = audit_log
        self._decisions_dir = decisions_dir or (output_dir / "decisions")

    def generate_agenda(
        self,
        *,
        meeting_id: str,
        week: str,
        watchlist: Iterable[Mapping[str, object]] | None = None,
        blocked: Iterable[Mapping[str, object]] | None = None,
    ) -> Path:
        watch_items = list(watchlist or [])
        blocked_items = list(blocked or [])
        content = self._render_agenda(meeting_id, week, watch_items, blocked_items)
        output_path = self._output_dir / f"{meeting_id}.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        self._append_audit(
            {
                "event": "audit.strategy_board_agenda",
                "meeting_id": meeting_id,
                "week": week,
                "path": str(output_path),
            }
        )
        return output_path

    def record_decision(
        self,
        *,
        meeting_id: str,
        strategy_id: str,
        decision: str,
        actor: str,
        notes: str | None = None,
    ) -> BoardDecision:
        entry = BoardDecision(
            meeting_id=meeting_id,
            strategy_id=strategy_id,
            decision=decision,
            actor=actor,
            notes=notes,
            recorded_at=_utcnow_iso(),
        )
        path = self._decisions_dir / f"{meeting_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.to_dict(), ensure_ascii=False))
            handle.write("\n")
        self._append_audit(
            {
                "event": "audit.strategy_board_decision",
                "meeting_id": meeting_id,
                "strategy_id": strategy_id,
                "decision": decision,
                "actor": actor,
            }
        )
        return entry

    def publish_summary(
        self,
        *,
        meeting_id: str,
        profile_id: str,
        channel: str = "local",
        dry_run: bool = False,
    ) -> dict[str, object]:
        report_path = self._output_dir / f"{meeting_id}.md"
        if not report_path.exists():
            raise FileNotFoundError(str(report_path))
        service = SecureShareService()
        package, manifest_path = service.prepare_package(
            profile_id=profile_id,
            period=meeting_id,
            sources=[report_path],
            include_internal=False,
            created_by="strategy_board",
        )
        encrypted_path = service.encrypt_package(package=package, manifest_path=manifest_path)
        if dry_run:
            return {
                "status": "dry_run",
                "package_id": package.package_id,
                "manifest_path": str(manifest_path),
                "encrypted_path": str(encrypted_path),
            }
        record = service.publish(
            package=package,
            encrypted_path=encrypted_path,
            channel=channel,
            notes=f"strategy_board_summary:{meeting_id}",
        )
        self._append_audit(
            {
                "event": "audit.strategy_board_summary_shared",
                "meeting_id": meeting_id,
                "profile_id": profile_id,
                "package_id": package.package_id,
                "channel": channel,
            }
        )
        return {"status": record.status, "package_id": package.package_id, "channel": channel}

    def _render_agenda(
        self,
        meeting_id: str,
        week: str,
        watchlist: list[Mapping[str, object]],
        blocked: list[Mapping[str, object]],
    ) -> str:
        if self._template_path.exists():
            template = self._template_path.read_text(encoding="utf-8")
        else:
            template = (
                "# Strategy Board Agenda\n"
                "- meeting_id: {{meeting_id}}\n"
                "- week: {{week}}\n"
                "\n## Watchlist\n{{watchlist}}\n\n## Blocked\n{{blocked}}\n"
            )
        watch_block = _render_list_block(watchlist) or "- none"
        blocked_block = _render_list_block(blocked) or "- none"
        return (
            template.replace("{{meeting_id}}", meeting_id)
            .replace("{{week}}", week)
            .replace("{{watchlist}}", watch_block)
            .replace("{{blocked}}", blocked_block)
            + "\n"
        )

    def _append_audit(self, payload: Mapping[str, object]) -> None:
        self._audit_log.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _utcnow_iso(), **payload}
        with self._audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")


def _render_list_block(items: Iterable[Mapping[str, object]]) -> str:
    lines = []
    for item in items:
        if not item:
            continue
        strategy_id = item.get("strategy_id") or item.get("id") or "unknown"
        score = item.get("alpha_score")
        extra = f" (alpha_score={score})" if score is not None else ""
        lines.append(f"- {strategy_id}{extra}")
    return "\n".join(lines)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["StrategyBoardService", "BoardDecision"]
