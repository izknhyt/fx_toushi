"""Persistence layer for broker order lifecycle and recovery plans."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml
try:
    import orjson
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    orjson = None

DEFAULT_ROOT = Path("orders")
DEFAULT_AUDIT_LOG = Path("logs/audit/order_state.jsonl")
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")


class OrderStoreError(RuntimeError):
    """Raised when order state persistence fails."""


@dataclass(slots=True)
class RecoveryAction:
    code: str
    label: str
    parameters: dict[str, Any] | None = None
    requires_manual: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "code": self.code,
            "label": self.label,
            "requires_manual": self.requires_manual,
        }
        if self.parameters:
            payload["parameters"] = dict(self.parameters)
        return payload


@dataclass(slots=True)
class RecoveryPlan:
    order_id: str
    plan_id: str
    trigger_reason: str
    actions: list[RecoveryAction]
    runbook_ref: str
    status: str
    assigned_to: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "plan_id": self.plan_id,
            "trigger_reason": self.trigger_reason,
            "actions": [action.to_dict() for action in self.actions],
            "assigned_to": self.assigned_to,
            "runbook_ref": self.runbook_ref,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "notes": list(self.notes),
        }


@dataclass(slots=True)
class OrderEnvelope:
    order_id: str
    external_id: str | None
    mode: str
    stage_guard_stage: str
    strategy_id: str | None
    ticket_id: str | None
    profile: str
    risk_snapshot: dict[str, Any]
    protect_pips: float | None
    reduce_only: bool
    submitted_by: str
    submitted_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OrderState:
    order_id: str
    status: str
    last_transition: str
    attempt: int
    evidence_hash: str
    error_code: str | None = None
    retry_after: int | None = None
    ack_received_at: str | None = None
    fill_summary: str | None = None
    recovery_plan: RecoveryPlan | None = None
    schema_version: str = "broker.order_state.v1"

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "order_id": self.order_id,
            "status": self.status,
            "last_transition": self.last_transition,
            "attempt": self.attempt,
            "error_code": self.error_code,
            "retry_after": self.retry_after,
            "ack_received_at": self.ack_received_at,
            "fill_summary": self.fill_summary,
            "evidence_hash": self.evidence_hash,
            "recovery_plan": self.recovery_plan.to_dict() if self.recovery_plan else None,
        }
        return payload


class FileLock:
    def __init__(self, path: Path, *, timeout_sec: float = 5.0) -> None:
        self._path = path
        self._timeout_sec = timeout_sec
        self._handle: Any | None = None

    def __enter__(self) -> "FileLock":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self._path.open("a", encoding="utf-8")
        start = time.monotonic()
        while True:
            try:
                _lock_file(self._handle)
                return self
            except BlockingIOError:
                if time.monotonic() - start > self._timeout_sec:
                    raise OrderStoreError(f"timeout acquiring lock {self._path}")
                time.sleep(0.05)

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._handle is None:
            return
        try:
            _unlock_file(self._handle)
        finally:
            self._handle.close()
            self._handle = None


class OrderStateStore:
    """Persist order envelopes and state snapshots to disk."""

    def __init__(
        self,
        *,
        root_dir: Path = DEFAULT_ROOT,
        audit_log_path: Path = DEFAULT_AUDIT_LOG,
        ops_worklog_path: Path = DEFAULT_OPS_WORKLOG,
    ) -> None:
        self._root_dir = root_dir
        self._audit_log_path = audit_log_path
        self._ops_worklog_path = ops_worklog_path

    def save_envelope(self, envelope: OrderEnvelope) -> Path:
        path = self._root_dir / envelope.mode / f"{envelope.order_id}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = envelope.to_dict()
        path.write_text(_yaml_dump(payload), encoding="utf-8")
        return path

    def save_state(self, state: OrderState, *, mode: str) -> Path:
        path = self._root_dir / mode / f"{datetime.now(timezone.utc):%Y%m%d}.jsonl"
        lock_path = path.with_suffix(".lock")
        record = state.to_dict()
        with FileLock(lock_path):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("ab") as handle:
                handle.write(_dump_bytes(record))
                handle.write(b"\n")
                handle.flush()
                os.fsync(handle.fileno())
        self._append_audit(
            {
                "event": "audit.order_state_saved",
                "ts": _utcnow_iso(),
                "order_id": state.order_id,
                "status": state.status,
                "evidence_hash": state.evidence_hash,
            }
        )
        return path

    def load(self, order_id: str, *, mode: str) -> tuple[OrderEnvelope | None, OrderState | None]:
        envelope_path = self._root_dir / mode / f"{order_id}.yaml"
        envelope: OrderEnvelope | None = None
        if envelope_path.exists():
            payload = yaml.safe_load(envelope_path.read_text(encoding="utf-8")) or {}
            envelope = _envelope_from_payload(order_id, payload)
        state = self._latest_state(order_id=order_id, mode=mode)
        return envelope, state

    def history(self, order_id: str, *, mode: str) -> list[OrderState]:
        states: list[OrderState] = []
        for path in sorted((self._root_dir / mode).glob("*.jsonl")):
            for record in _read_jsonl(path):
                if str(record.get("order_id")) != order_id:
                    continue
                states.append(_state_from_payload(record))
        return states

    def list(
        self,
        *,
        mode: str,
        status_in: Iterable[str] | None = None,
        strategy_id: str | None = None,
    ) -> list[tuple[OrderEnvelope | None, OrderState]]:
        latest: dict[str, OrderState] = {}
        for path in sorted((self._root_dir / mode).glob("*.jsonl")):
            for record in _read_jsonl(path):
                order_id = str(record.get("order_id") or "")
                if not order_id:
                    continue
                latest[order_id] = _state_from_payload(record)
        status_filter = {status for status in status_in or []}
        results: list[tuple[OrderEnvelope | None, OrderState]] = []
        for order_id, state in latest.items():
            if status_filter and state.status not in status_filter:
                continue
            envelope_path = self._root_dir / mode / f"{order_id}.yaml"
            envelope = None
            if envelope_path.exists():
                payload = yaml.safe_load(envelope_path.read_text(encoding="utf-8")) or {}
                envelope = _envelope_from_payload(order_id, payload)
                if strategy_id and envelope.strategy_id != strategy_id:
                    continue
            results.append((envelope, state))
        return results

    def lock(self, order_id: str, *, mode: str, timeout_sec: float = 5.0) -> FileLock:
        lock_path = self._root_dir / mode / f"{order_id}.lock"
        return FileLock(lock_path, timeout_sec=timeout_sec)

    def cleanup(self, *, days: int = 90) -> list[Path]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        archived: list[Path] = []
        for mode_dir in self._root_dir.glob("*"):
            if not mode_dir.is_dir():
                continue
            for path in mode_dir.glob("*.jsonl"):
                if datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc) > cutoff:
                    continue
                target_dir = Path("archive") / "orders" / f"{cutoff:%Y%m}"
                target_dir.mkdir(parents=True, exist_ok=True)
                dest = target_dir / path.name
                checksum_path = target_dir / "checksums" / f"order_states_{cutoff:%Y%m}.sha256"
                checksum_path.parent.mkdir(parents=True, exist_ok=True)
                checksum = _sha256_file(path)
                with checksum_path.open("a", encoding="utf-8") as handle:
                    handle.write(f"{checksum}  {path.name}\n")
                shutil.move(str(path), dest)
                archived.append(dest)
        if archived:
            self._append_ops_worklog(
                {
                    "timestamp": _utcnow_iso(),
                    "task": "order_state_archive",
                    "status": "completed",
                    "archived": len(archived),
                    "paths": [str(path) for path in archived],
                }
            )
        return archived

    def _latest_state(self, *, order_id: str, mode: str) -> OrderState | None:
        latest: OrderState | None = None
        for path in sorted((self._root_dir / mode).glob("*.jsonl")):
            for record in _read_jsonl(path):
                if str(record.get("order_id")) != order_id:
                    continue
                latest = _state_from_payload(record)
        return latest

    def _append_audit(self, payload: Mapping[str, Any]) -> None:
        self._audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_log_path.open("a", encoding="utf-8") as handle:
            handle.write(_dump_text(payload))
            handle.write("\n")

    def _append_ops_worklog(self, payload: Mapping[str, Any]) -> None:
        self._ops_worklog_path.parent.mkdir(parents=True, exist_ok=True)
        with self._ops_worklog_path.open("ab") as handle:
            handle.write(_dump_bytes(payload))
            handle.write(b"\n")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_bytes().splitlines():
        record = _load_line(line)
        if record is not None:
            records.append(record)
    return records


def _envelope_from_payload(order_id: str, payload: Mapping[str, Any]) -> OrderEnvelope:
    return OrderEnvelope(
        order_id=order_id,
        external_id=payload.get("external_id"),
        mode=str(payload.get("mode", "paper")),
        stage_guard_stage=str(payload.get("stage_guard_stage", "manual_only")),
        strategy_id=payload.get("strategy_id"),
        ticket_id=payload.get("ticket_id"),
        profile=str(payload.get("profile", "paper")),
        risk_snapshot=dict(payload.get("risk_snapshot") or {}),
        protect_pips=payload.get("protect_pips"),
        reduce_only=bool(payload.get("reduce_only", False)),
        submitted_by=str(payload.get("submitted_by", "system")),
        submitted_at=str(payload.get("submitted_at", _utcnow_iso())),
    )


def _state_from_payload(payload: Mapping[str, Any]) -> OrderState:
    recovery_payload = payload.get("recovery_plan")
    recovery = None
    if isinstance(recovery_payload, Mapping):
        recovery = RecoveryPlan(
            order_id=str(recovery_payload.get("order_id")),
            plan_id=str(recovery_payload.get("plan_id")),
            trigger_reason=str(recovery_payload.get("trigger_reason")),
            actions=[
                RecoveryAction(
                    code=str(action.get("code")),
                    label=str(action.get("label")),
                    parameters=dict(action.get("parameters") or {})
                    if isinstance(action, Mapping)
                    else None,
                    requires_manual=bool(action.get("requires_manual", False))
                    if isinstance(action, Mapping)
                    else False,
                )
                for action in recovery_payload.get("actions") or []
                if isinstance(action, Mapping)
            ],
            runbook_ref=str(recovery_payload.get("runbook_ref")),
            status=str(recovery_payload.get("status")),
            assigned_to=recovery_payload.get("assigned_to"),
            created_at=recovery_payload.get("created_at"),
            updated_at=recovery_payload.get("updated_at"),
            notes=list(recovery_payload.get("notes") or []),
        )
    return OrderState(
        order_id=str(payload.get("order_id")),
        status=str(payload.get("status")),
        last_transition=str(payload.get("last_transition")),
        attempt=int(payload.get("attempt", 1)),
        evidence_hash=str(payload.get("evidence_hash")),
        error_code=payload.get("error_code"),
        retry_after=payload.get("retry_after"),
        ack_received_at=payload.get("ack_received_at"),
        fill_summary=payload.get("fill_summary"),
        recovery_plan=recovery,
        schema_version=str(payload.get("schema_version") or "broker.order_state.v1"),
    )


def _lock_file(handle: Any) -> None:
    try:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except ModuleNotFoundError:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            raise


def _unlock_file(handle: Any) -> None:
    try:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except ModuleNotFoundError:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            raise


def _dump_bytes(payload: Mapping[str, Any]) -> bytes:
    if orjson is not None:
        return orjson.dumps(payload)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _dump_text(payload: Mapping[str, Any]) -> str:
    if orjson is not None:
        return orjson.dumps(payload).decode("utf-8")
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _load_line(line: bytes) -> dict[str, Any] | None:
    if not line.strip():
        return None
    try:
        if orjson is not None:
            return orjson.loads(line)
        return json.loads(line.decode("utf-8"))
    except (json.JSONDecodeError, ValueError):
        return None


def _yaml_dump(payload: Mapping[str, Any]) -> str:
    dumper = getattr(yaml, "safe_dump", None) or getattr(yaml, "dump", None)
    if dumper is None:
        return "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    return str(dumper(payload, sort_keys=False))


__all__ = [
    "OrderEnvelope",
    "OrderState",
    "OrderStateStore",
    "RecoveryAction",
    "RecoveryPlan",
]
