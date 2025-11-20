"""Strategy Scoreboard Service implementation (detailed design §3.25, appendix G.1)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from src.ops.profit_readiness import DEFAULT_PROFIT_READINESS_PATH, ProfitReadinessEntry, record_readiness
from src.scoreboard.bridge import ScoreboardBridge, ScoreboardBridgeSnapshot

logger = logging.getLogger(__name__)

DEFAULT_ALPHA_DIR = Path("scoreboard") / "alpha"
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")
DEFAULT_WATCHLIST_LOG = Path("logs") / "scoreboard_watchlist.jsonl"
DEFAULT_PROFIT_LOOP_REPORT = Path("reports/performance/profit_loop_daily.md")


class ScoreboardComputationFailed(RuntimeError):
    """Raised when the scoreboard snapshot cannot be generated."""


@dataclass(frozen=True)
class WatchlistRecord:
    """Captures a scored watchlist entry for auditing."""

    strategy_id: str
    reasons: tuple[str, ...]
    snapshot_week: str
    evidence: tuple[str, ...]

    def to_mapping(self, *, timestamp: str) -> Mapping[str, object]:
        return {
            "timestamp": timestamp,
            "strategy_id": self.strategy_id,
            "snapshot_week": self.snapshot_week,
            "reasons": list(self.reasons),
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class SnapshotSummary:
    """Aggregate status derived from a bridge snapshot."""

    status: str
    watchlist_records: tuple[WatchlistRecord, ...]
    advisory_strategies: tuple[str, ...]


class StrategyScoreboardService:
    """Wraps the bridge generator with persistence, readiness, and watchlist hooks."""

    def __init__(
        self,
        *,
        bridge: ScoreboardBridge | None = None,
        alpha_dir: Path = DEFAULT_ALPHA_DIR,
        profit_readiness_path: Path = DEFAULT_PROFIT_READINESS_PATH,
        ops_worklog_path: Path = DEFAULT_OPS_WORKLOG,
        watchlist_log_path: Path = DEFAULT_WATCHLIST_LOG,
        profit_loop_report: Path = DEFAULT_PROFIT_LOOP_REPORT,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._bridge = bridge or ScoreboardBridge()
        self._alpha_dir = alpha_dir
        self._profit_readiness_path = profit_readiness_path
        self._ops_worklog_path = ops_worklog_path
        self._watchlist_log_path = watchlist_log_path
        self._profit_loop_report = profit_loop_report
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def generate_weekly_snapshot(
        self,
        *,
        week: str | None = None,
        mode: str = "live",
        actor: str | None = None,
        runbooks: Sequence[str] | None = None,
        command: str | None = None,
    ) -> ScoreboardBridgeSnapshot:
        """Generate/export a scoreboard snapshot and update readiness artefacts."""

        target_week = week or self._clock().strftime("%Y-W%V")
        snapshot = self._bridge.generate(week=target_week, mode=mode)
        bridge_path = self._bridge.export(snapshot)
        alpha_path = self._write_alpha_snapshot(snapshot, bridge_path=bridge_path)
        summary = self._summarise_snapshot(snapshot, evidence_paths=(alpha_path, bridge_path))
        readiness = self._record_profit_readiness(
            summary=summary,
            alpha_path=alpha_path,
            bridge_path=bridge_path,
            actor=actor,
        )
        self._append_ops_worklog(
            snapshot=snapshot,
            alpha_path=alpha_path,
            bridge_path=bridge_path,
            runbooks=runbooks,
            command=command,
            readiness=readiness,
        )
        self._log_watchlist_records(summary.watchlist_records)
        logger.info(
            "scoreboard.service.snapshot_generated",
            extra={
                "week": snapshot.week,
                "mode": snapshot.mode,
                "status": summary.status,
                "watchlist": [record.strategy_id for record in summary.watchlist_records],
            },
        )
        return snapshot

    def get_latest(self) -> Mapping[str, object] | None:
        """Return the most recent alpha snapshot payload."""

        if not self._alpha_dir.exists():
            return None
        candidates = sorted(self._alpha_dir.glob("*.json"))
        if not candidates:
            return None
        target = candidates[-1]
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ScoreboardComputationFailed(f"Alpha snapshot malformed: {target}") from exc

    def trigger_watchlist(
        self,
        *,
        strategy_id: str,
        reasons: Iterable[str],
        snapshot_week: str,
        evidence: Iterable[str] | None = None,
    ) -> None:
        """Persist a manual watchlist trigger entry."""

        record = WatchlistRecord(
            strategy_id=strategy_id,
            reasons=tuple(reasons),
            snapshot_week=snapshot_week,
            evidence=tuple(evidence or ()),
        )
        self._log_watchlist_records((record,))

    def _write_alpha_snapshot(self, snapshot: ScoreboardBridgeSnapshot, *, bridge_path: Path) -> Path:
        payload = snapshot.to_mapping()
        alpha_path = self._alpha_dir / f"{snapshot.week}.json"
        alpha_path.parent.mkdir(parents=True, exist_ok=True)
        for entry in payload.get("strategies", []):
            evidence = entry.setdefault("evidence", [])
            if isinstance(evidence, list):
                if str(bridge_path) not in evidence:
                    evidence.append(str(bridge_path))
                if str(alpha_path) not in evidence:
                    evidence.append(str(alpha_path))
        alpha_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return alpha_path

    def _summarise_snapshot(
        self,
        snapshot: ScoreboardBridgeSnapshot,
        *,
        evidence_paths: Sequence[Path],
    ) -> SnapshotSummary:
        watchlist: list[WatchlistRecord] = []
        advisory: list[str] = []
        overall_status = "ok"
        evidence = tuple(str(path) for path in evidence_paths if path)

        for entry in snapshot.strategies:
            reasons = tuple(entry.watchlist_reasons)
            if reasons:
                watchlist.append(
                    WatchlistRecord(
                        strategy_id=entry.strategy_id,
                        reasons=reasons,
                        snapshot_week=snapshot.week,
                        evidence=evidence,
                    )
                )
                overall_status = "alert"
            elif entry.status != "ok":
                advisory.append(entry.strategy_id)
                if overall_status != "alert":
                    overall_status = "warning"

        return SnapshotSummary(
            status=overall_status,
            watchlist_records=tuple(watchlist),
            advisory_strategies=tuple(advisory),
        )

    def _record_profit_readiness(
        self,
        *,
        summary: SnapshotSummary,
        alpha_path: Path,
        bridge_path: Path,
        actor: str | None,
    ) -> ProfitReadinessEntry:
        evidence: list[str] = [str(alpha_path), str(bridge_path)]
        if self._profit_loop_report.exists():
            evidence.append(str(self._profit_loop_report))
        notes_parts: list[str] = []
        if summary.watchlist_records:
            for record in summary.watchlist_records:
                joined = ", ".join(record.reasons)
                notes_parts.append(f"{record.strategy_id}: {joined}")
        if summary.advisory_strategies:
            advisory = ", ".join(summary.advisory_strategies)
            notes_parts.append(f"advisory={advisory}")
        notes = "; ".join(notes_parts) if notes_parts else None
        return record_readiness(
            lever="Alpha Feedback & Scoreboard",
            status=summary.status,
            evidence=evidence,
            notes=notes,
            actor=actor,
            path=self._profit_readiness_path,
        )

    def _append_ops_worklog(
        self,
        *,
        snapshot: ScoreboardBridgeSnapshot,
        alpha_path: Path,
        bridge_path: Path,
        runbooks: Sequence[str] | None,
        command: str | None,
        readiness: ProfitReadinessEntry,
    ) -> None:
        entry = {
            "timestamp": readiness.timestamp,
            "task": "alpha_bridge",
            "week": snapshot.week,
            "mode": snapshot.mode,
            "runbooks": list(runbooks or []),
            "command": command,
            "evidence": str(alpha_path),
            "bridge": str(bridge_path),
            "status": readiness.status,
            "notes": readiness.notes,
        }
        self._ops_worklog_path.parent.mkdir(parents=True, exist_ok=True)
        with self._ops_worklog_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _log_watchlist_records(self, records: Iterable[WatchlistRecord]) -> None:
        items = tuple(records)
        if not items:
            return
        timestamp = self._clock().replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self._watchlist_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._watchlist_log_path.open("a", encoding="utf-8") as handle:
            for record in items:
                handle.write(json.dumps(record.to_mapping(timestamp=timestamp), ensure_ascii=False) + "\n")


__all__ = [
    "DEFAULT_ALPHA_DIR",
    "DEFAULT_OPS_WORKLOG",
    "DEFAULT_PROFIT_LOOP_REPORT",
    "DEFAULT_WATCHLIST_LOG",
    "ScoreboardComputationFailed",
    "SnapshotSummary",
    "StrategyScoreboardService",
    "WatchlistRecord",
]
