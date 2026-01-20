"""BackOffice ledger service (EP07-BO-P1)."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

DEFAULT_EVENT_DIR = Path("logs") / "events"
DEFAULT_LEDGER_PARQUET_DIR = Path("parquet") / "backoffice"
DEFAULT_LEDGER_JSONL_DIR = Path("jsonl") / "backoffice"
DEFAULT_SNAPSHOT_DIR = Path("snapshots") / "backoffice"
DEFAULT_REPORT_DIR = Path("reports") / "tax"
DEFAULT_METRICS_PATH = Path("metrics") / "backoffice_ledger.jsonl"
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")
DEFAULT_LEDGER_TEMPLATE = DEFAULT_REPORT_DIR / "ledger_summary_TEMPLATE.md"

SUPPORTED_EVENTS = {
    "ticket.approved",
    "execution.filled",
    "funding.applied",
    "reconciliation.discrepancy",
}


class LedgerError(RuntimeError):
    """Base error for ledger operations."""


class LedgerPeriodError(LedgerError):
    """Raised when the period argument is invalid."""


class LedgerSourceMissing(LedgerError):
    """Raised when ledger sources are missing."""


class AdjustmentSignatureError(LedgerError):
    """Raised when an adjustment record is missing a signature."""


class LedgerExportError(LedgerError):
    """Raised when ledger export fails."""


class AuditAttachmentError(LedgerError):
    """Raised when audit bundle attachment fails."""


@dataclass(slots=True)
class LedgerEntry:
    entry_id: str
    trade_id: str | None
    mode: str
    symbol: str
    side: str
    opened_at: str | None
    closed_at: str | None
    gross_pnl: float
    fees: float
    swap: float
    tax_category: str
    source_event_id: str
    statement_ref: str | None
    reconciliation_status: str
    notes: str | None


@dataclass(slots=True)
class LedgerSnapshot:
    generated_at: str
    mode: str
    period: str
    entries_hash: str
    statement_hash: str | None
    schema_version: str
    entries_total: int
    pending_entries: int
    parquet_path: str
    jsonl_path: str
    taxlots_path: str
    snapshot_path: str
    summary_path: str


@dataclass(slots=True)
class TaxLot:
    lot_id: str
    symbol: str
    open_entry_id: str
    close_entry_id: str | None
    quantity: float
    pnl: float
    holding_period_days: int
    category: str


@dataclass(slots=True)
class AdjustmentRecord:
    adjustment_id: str
    period: str
    mode: str
    type: str
    amount: float
    created_by: str
    reason: str
    supporting_document: str | None
    signed_by: str
    signature: str
    created_at: str


@dataclass(slots=True)
class AdjustmentReceipt:
    adjustment_id: str
    ledger_entry_id: str
    applied_at: str
    period: str
    mode: str
    audit_path: str


class BackOfficeLedgerService:
    """Generate ledger snapshots for backoffice/tax reporting."""

    def __init__(
        self,
        *,
        event_dir: Path = DEFAULT_EVENT_DIR,
        parquet_dir: Path = DEFAULT_LEDGER_PARQUET_DIR,
        jsonl_dir: Path = DEFAULT_LEDGER_JSONL_DIR,
        snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
        report_dir: Path = DEFAULT_REPORT_DIR,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        ops_worklog_path: Path = DEFAULT_OPS_WORKLOG,
        template_path: Path = DEFAULT_LEDGER_TEMPLATE,
    ) -> None:
        self._event_dir = event_dir
        self._parquet_dir = parquet_dir
        self._jsonl_dir = jsonl_dir
        self._snapshot_dir = snapshot_dir
        self._report_dir = report_dir
        self._metrics_path = metrics_path
        self._ops_worklog_path = ops_worklog_path
        self._template_path = template_path

    def generate(self, *, period: str, mode: str, include_pending: bool = True) -> LedgerSnapshot:
        started_at = time.monotonic()
        start, end = _parse_period(period)
        events = list(_collect_events(self._event_dir, start, end, mode=mode))
        if not events:
            raise LedgerSourceMissing("no events found for period")
        entries = _build_entries(events)
        if not include_pending:
            entries = [entry for entry in entries if entry.reconciliation_status == "matched"]
        parquet_path = self._parquet_dir / f"ledger_{mode}_{period}.parquet"
        jsonl_path = self._jsonl_dir / f"ledger_{mode}_{period}.jsonl"
        taxlots_path = self._jsonl_dir / f"taxlots_{period}.jsonl"
        summary_path = self._report_dir / f"ledger_summary_{period}.md"
        snapshot_path = self._snapshot_dir / f"ledger_{_ts_compact()}.json"

        self._parquet_dir.mkdir(parents=True, exist_ok=True)
        self._jsonl_dir.mkdir(parents=True, exist_ok=True)
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._report_dir.mkdir(parents=True, exist_ok=True)

        pd.DataFrame([asdict(entry) for entry in entries]).to_parquet(parquet_path, index=False)
        with jsonl_path.open("w", encoding="utf-8") as handle:
            for entry in entries:
                payload = asdict(entry)
                payload["period"] = period
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")

        taxlots = _build_taxlots(entries)
        with taxlots_path.open("w", encoding="utf-8") as handle:
            for lot in taxlots:
                payload = asdict(lot)
                payload["period"] = period
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")

        entries_hash = _hash_entries(entries)
        snapshot = LedgerSnapshot(
            generated_at=_utcnow_iso(),
            mode=mode,
            period=period,
            entries_hash=entries_hash,
            statement_hash=None,
            schema_version="backoffice_ledger_snapshot.v1",
            entries_total=len(entries),
            pending_entries=sum(1 for entry in entries if entry.reconciliation_status != "matched"),
            parquet_path=str(parquet_path),
            jsonl_path=str(jsonl_path),
            taxlots_path=str(taxlots_path),
            snapshot_path=str(snapshot_path),
            summary_path=str(summary_path),
        )
        snapshot_path.write_text(json.dumps(asdict(snapshot), ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_summary(snapshot, template_path=self._template_path)
        duration_ms = int((time.monotonic() - started_at) * 1000)
        self._append_metrics(snapshot, taxlots_total=len(taxlots), adjustments_applied=0, duration_ms=duration_ms)
        self._append_worklog(period, mode, duration_min=max(1, round(duration_ms / 60000)))
        self._append_audit_event(
            {
                "event": "audit.backoffice_ledger_generated",
                "period": period,
                "mode": mode,
                "entries_total": snapshot.entries_total,
                "pending_entries": snapshot.pending_entries,
                "ledger_hash": snapshot.entries_hash,
                "taxlots_total": len(taxlots),
            }
        )
        return snapshot

    def _write_summary(self, snapshot: LedgerSnapshot, *, template_path: Path) -> None:
        if not template_path.exists():
            content = _render_default_summary(snapshot)
        else:
            content = template_path.read_text(encoding="utf-8").format(
                period=snapshot.period,
                mode=snapshot.mode,
                entries_total=snapshot.entries_total,
                pending_entries=snapshot.pending_entries,
                ledger_parquet_path=snapshot.parquet_path,
                ledger_jsonl_path=snapshot.jsonl_path,
                taxlots_path=snapshot.taxlots_path,
                snapshot_path=snapshot.snapshot_path,
            )
        summary_path = self._report_dir / f"ledger_summary_{snapshot.period}.md"
        summary_path.write_text(content, encoding="utf-8")

    def _append_metrics(
        self,
        snapshot: LedgerSnapshot,
        *,
        taxlots_total: int,
        adjustments_applied: int,
        duration_ms: int,
    ) -> None:
        payload = {
            "ts": snapshot.generated_at,
            "period": snapshot.period,
            "mode": snapshot.mode,
            "entries_total": snapshot.entries_total,
            "pending_entries": snapshot.pending_entries,
            "reconciliation_variance": snapshot.pending_entries,
            "taxlots_generated": taxlots_total,
            "adjustments_applied": adjustments_applied,
            "generation_duration_ms": duration_ms,
        }
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _append_worklog(self, period: str, mode: str, *, duration_min: int) -> None:
        payload = {
            "ts": _utcnow_iso(),
            "task": "ledger_generate",
            "period": period,
            "mode": mode,
            "duration_min": duration_min,
        }
        self._ops_worklog_path.parent.mkdir(parents=True, exist_ok=True)
        with self._ops_worklog_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def apply_adjustment(self, record: AdjustmentRecord) -> AdjustmentReceipt:
        if not record.signature:
            raise AdjustmentSignatureError("missing adjustment signature")
        ledger_entries = _load_ledger_entries(
            self._parquet_dir / f"ledger_{record.mode}_{record.period}.parquet"
        )
        adjustment_entry = _adjustment_to_entry(record)
        ledger_entries.append(adjustment_entry)
        parquet_path = self._parquet_dir / f"ledger_{record.mode}_{record.period}.parquet"
        jsonl_path = self._jsonl_dir / f"ledger_{record.mode}_{record.period}.jsonl"
        taxlots_path = self._jsonl_dir / f"taxlots_{record.period}.jsonl"
        snapshot_path = self._snapshot_dir / f"ledger_{_ts_compact()}.json"
        summary_path = self._report_dir / f"ledger_summary_{record.period}.md"

        self._parquet_dir.mkdir(parents=True, exist_ok=True)
        self._jsonl_dir.mkdir(parents=True, exist_ok=True)
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._report_dir.mkdir(parents=True, exist_ok=True)

        pd.DataFrame([asdict(entry) for entry in ledger_entries]).to_parquet(parquet_path, index=False)
        with jsonl_path.open("w", encoding="utf-8") as handle:
            for entry in ledger_entries:
                payload = asdict(entry)
                payload["period"] = record.period
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")

        taxlots = _build_taxlots(ledger_entries)
        with taxlots_path.open("w", encoding="utf-8") as handle:
            for lot in taxlots:
                payload = asdict(lot)
                payload["period"] = record.period
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")

        snapshot = LedgerSnapshot(
            generated_at=_utcnow_iso(),
            mode=record.mode,
            period=record.period,
            entries_hash=_hash_entries(ledger_entries),
            statement_hash=None,
            schema_version="backoffice_ledger_snapshot.v1",
            entries_total=len(ledger_entries),
            pending_entries=sum(1 for entry in ledger_entries if entry.reconciliation_status != "matched"),
            parquet_path=str(parquet_path),
            jsonl_path=str(jsonl_path),
            taxlots_path=str(taxlots_path),
            snapshot_path=str(snapshot_path),
            summary_path=str(summary_path),
        )
        snapshot_path.write_text(json.dumps(asdict(snapshot), ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_summary(snapshot, template_path=self._template_path)
        self._append_metrics(
            snapshot,
            taxlots_total=len(taxlots),
            adjustments_applied=1,
            duration_ms=0,
        )
        audit_path = self._append_audit_event(
            {
                "event": "audit.backoffice_adjustment",
                "period": record.period,
                "mode": record.mode,
                "adjustment_id": record.adjustment_id,
                "amount": record.amount,
                "signed_by": record.signed_by,
                "signature": record.signature,
            }
        )
        return AdjustmentReceipt(
            adjustment_id=record.adjustment_id,
            ledger_entry_id=adjustment_entry.entry_id,
            applied_at=_utcnow_iso(),
            period=record.period,
            mode=record.mode,
            audit_path=audit_path,
        )

    def export(
        self,
        *,
        period: str,
        mode: str,
        format: str,
        scope: str,
        output: Path | None = None,
    ) -> Path:
        format_value = format.lower()
        scope_value = scope.lower()
        if scope_value not in {"ledger", "taxlots"}:
            raise LedgerExportError(f"unknown export scope: {scope}")
        if format_value not in {"parquet", "json", "csv"}:
            raise LedgerExportError(f"unknown export format: {format}")
        if scope_value == "ledger":
            parquet_path = self._parquet_dir / f"ledger_{mode}_{period}.parquet"
            jsonl_path = self._jsonl_dir / f"ledger_{mode}_{period}.jsonl"
            if format_value == "parquet":
                return parquet_path
            if format_value == "json":
                return jsonl_path
            frame = _load_frame(parquet_path)
        else:
            jsonl_path = self._jsonl_dir / f"taxlots_{period}.jsonl"
            if format_value == "json":
                return jsonl_path
            frame = _load_jsonl_frame(jsonl_path)

        if output is None:
            output = self._report_dir / f"{scope_value}_{mode}_{period}.{format_value}"
        output.parent.mkdir(parents=True, exist_ok=True)
        if format_value == "csv":
            frame.to_csv(output, index=False)
        else:
            frame.to_parquet(output, index=False)
        return output

    def sync_with_audit_bundle(self, *, bundle_id: str, period: str, mode: str) -> str:
        bundle_root = Path("audit_pack") / bundle_id / "finance"
        if not bundle_root.parent.exists():
            raise AuditAttachmentError(f"audit bundle not found: {bundle_root.parent}")
        bundle_root.mkdir(parents=True, exist_ok=True)
        attachments = [
            self._parquet_dir / f"ledger_{mode}_{period}.parquet",
            self._jsonl_dir / f"ledger_{mode}_{period}.jsonl",
            self._report_dir / f"ledger_summary_{period}.md",
        ]
        missing = [str(path) for path in attachments if not path.exists()]
        if missing:
            raise AuditAttachmentError(f"missing finance artifacts: {', '.join(missing)}")
        for path in attachments:
            dest = bundle_root / path.name
            dest.write_bytes(path.read_bytes())
        return str(bundle_root)

    def _append_audit_event(self, payload: Mapping[str, object]) -> str:
        audit_path = _audit_log_path()
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        payload_with_ts = {"ts": _utcnow_iso(), **payload}
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload_with_ts, ensure_ascii=False))
            handle.write("\n")
        return str(audit_path)


def _parse_period(period: str) -> tuple[datetime, datetime]:
    text = period.strip()
    if len(text) == 6 and text.isdigit():
        start = datetime(int(text[:4]), int(text[4:6]), 1, tzinfo=timezone.utc)
        if start.month == 12:
            end = datetime(start.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(start.year, start.month + 1, 1, tzinfo=timezone.utc)
        return start, end
    if len(text) == 4 and text.isdigit():
        start = datetime(int(text), 1, 1, tzinfo=timezone.utc)
        end = datetime(int(text) + 1, 1, 1, tzinfo=timezone.utc)
        return start, end
    raise LedgerPeriodError(f"invalid period: {period}")


def _collect_events(
    event_dir: Path,
    start: datetime,
    end: datetime,
    *,
    mode: str,
) -> Iterable[dict[str, object]]:
    if not event_dir.exists():
        return []
    for path in sorted(event_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            event_name = str(payload.get("event", ""))
            if event_name not in SUPPORTED_EVENTS:
                continue
            ts = _parse_ts(payload.get("ts"))
            if ts is None:
                continue
            if ts < start or ts >= end:
                continue
            event_mode = payload.get("mode") or payload.get("payload", {}).get("mode")
            if event_mode:
                if str(event_mode) != mode:
                    continue
            elif mode != "live":
                continue
            yield payload


def _build_entries(events: Iterable[dict[str, object]]) -> list[LedgerEntry]:
    entries: list[LedgerEntry] = []
    for event in events:
        event_name = str(event.get("event"))
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        mode = str(payload.get("mode") or event.get("mode") or "live")
        symbol = str(payload.get("symbol") or event.get("symbol") or "n/a")
        side = str(payload.get("side") or event.get("side") or "n/a")
        trade_id = payload.get("trade_id") or payload.get("execution_id") or event.get("trade_id")
        source_event_id = str(event.get("event_id") or event.get("id") or event_name)
        opened_at = _to_iso(payload.get("opened_at") or payload.get("open_ts"))
        closed_at = _to_iso(payload.get("closed_at") or payload.get("close_ts"))
        gross_pnl = _coerce_float(_first_present(payload.get("gross_pnl"), payload.get("pnl")))
        fees = _coerce_float(payload.get("fees"))
        swap = _coerce_float(_first_present(payload.get("swap"), payload.get("amount")))
        tax_category = "spot_fx"
        reconciliation_status = str(payload.get("reconciliation_status") or "pending")
        notes = None

        if event_name == "funding.applied":
            tax_category = "swap_income"
            reconciliation_status = "matched"
        elif event_name == "ticket.approved":
            tax_category = "other"
            reconciliation_status = "pending"
            notes = "ticket approval"
        elif event_name == "reconciliation.discrepancy":
            tax_category = "other"
            reconciliation_status = "variance"
            notes = str(payload.get("reason") or "reconciliation discrepancy")

        entry_id = _hash_text(
            f"{event_name}:{trade_id}:{symbol}:{mode}:{event.get('ts')}"
        )
        entries.append(
            LedgerEntry(
                entry_id=entry_id,
                trade_id=str(trade_id) if trade_id is not None else None,
                mode=mode,
                symbol=symbol,
                side=side,
                opened_at=opened_at,
                closed_at=closed_at,
                gross_pnl=gross_pnl,
                fees=fees,
                swap=swap,
                tax_category=tax_category,
                source_event_id=source_event_id,
                statement_ref=None,
                reconciliation_status=reconciliation_status,
                notes=notes,
            )
        )
    return entries


def _build_taxlots(entries: Iterable[LedgerEntry]) -> list[TaxLot]:
    taxlots: list[TaxLot] = []
    for entry in entries:
        if entry.reconciliation_status == "pending":
            continue
        pnl = entry.gross_pnl - entry.fees + entry.swap
        lot_id = _hash_text(f"lot:{entry.entry_id}")
        taxlots.append(
            TaxLot(
                lot_id=lot_id,
                symbol=entry.symbol,
                open_entry_id=entry.entry_id,
                close_entry_id=None,
                quantity=0.0,
                pnl=pnl,
                holding_period_days=0,
                category="short_term",
            )
        )
    return taxlots


def _render_default_summary(snapshot: LedgerSnapshot) -> str:
    return "\n".join(
        [
            f"# Ledger Summary ({snapshot.period})",
            "",
            f"- Mode: {snapshot.mode}",
            f"- Entries: {snapshot.entries_total}",
            f"- Pending: {snapshot.pending_entries}",
            f"- Parquet: {snapshot.parquet_path}",
            f"- JSONL: {snapshot.jsonl_path}",
            f"- TaxLots: {snapshot.taxlots_path}",
            f"- Snapshot: {snapshot.snapshot_path}",
        ]
    )


def _hash_entries(entries: Iterable[LedgerEntry]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(entry.entry_id.encode("utf-8"))
    return f"sha256:{digest.hexdigest()}"


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_ts(value: object | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _to_iso(value: object | None) -> str | None:
    if value is None:
        return None
    dt = _parse_ts(value)
    if dt is None:
        return str(value)
    return dt.isoformat().replace("+00:00", "Z")


def _first_present(*values: object | None) -> object | None:
    for value in values:
        if value is not None:
            return value
    return None


def _coerce_float(value: object | None, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_ledger_entries(path: Path) -> list[LedgerEntry]:
    if not path.exists():
        raise LedgerSourceMissing(f"ledger parquet missing: {path}")
    frame = pd.read_parquet(path)
    entries = []
    for record in frame.to_dict(orient="records"):
        entries.append(
            LedgerEntry(
                entry_id=str(record.get("entry_id")),
                trade_id=record.get("trade_id"),
                mode=str(record.get("mode")),
                symbol=str(record.get("symbol")),
                side=str(record.get("side")),
                opened_at=record.get("opened_at"),
                closed_at=record.get("closed_at"),
                gross_pnl=float(record.get("gross_pnl") or 0.0),
                fees=float(record.get("fees") or 0.0),
                swap=float(record.get("swap") or 0.0),
                tax_category=str(record.get("tax_category") or "spot_fx"),
                source_event_id=str(record.get("source_event_id") or ""),
                statement_ref=record.get("statement_ref"),
                reconciliation_status=str(record.get("reconciliation_status") or "pending"),
                notes=record.get("notes"),
            )
        )
    return entries


def _adjustment_to_entry(record: AdjustmentRecord) -> LedgerEntry:
    entry_id = _hash_text(f"adjustment:{record.adjustment_id}:{record.period}:{record.mode}")
    category = "expense" if record.type in {"broker_fee", "tax_adjustment"} else "other"
    gross_pnl = -abs(record.amount) if record.amount >= 0 else record.amount
    return LedgerEntry(
        entry_id=entry_id,
        trade_id=None,
        mode=record.mode,
        symbol="n/a",
        side="n/a",
        opened_at=None,
        closed_at=None,
        gross_pnl=gross_pnl,
        fees=0.0,
        swap=0.0,
        tax_category=category,
        source_event_id=f"adjustment:{record.adjustment_id}",
        statement_ref=None,
        reconciliation_status="matched",
        notes=record.reason,
    )


def _load_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise LedgerExportError(f"missing source: {path}")
    return pd.read_parquet(path)


def _load_jsonl_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise LedgerExportError(f"missing source: {path}")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return pd.DataFrame(rows)


def _audit_log_path() -> Path:
    return Path("logs") / "audit" / f"backoffice_{datetime.now(timezone.utc):%Y%m%d}.jsonl"


def parse_adjustments_markdown(path: Path, *, period: str, mode: str) -> list[AdjustmentRecord]:
    if not path.exists():
        raise LedgerSourceMissing(f"adjustments file missing: {path}")
    records: list[AdjustmentRecord] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if "|" not in line or line.strip().startswith("| ---"):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) < 5 or parts[0].lower() == "adjustment id":
            continue
        adjustment_id = parts[0]
        record_type = parts[1]
        amount = _coerce_float(parts[2])
        created_by = parts[3] or "unknown"
        reason = parts[4] or ""
        supporting_document = parts[5] if len(parts) > 5 and parts[5] else None
        signed_by = parts[6] if len(parts) > 6 else created_by
        signature = parts[7] if len(parts) > 7 else ""
        records.append(
            AdjustmentRecord(
                adjustment_id=adjustment_id,
                period=period,
                mode=mode,
                type=record_type,
                amount=amount,
                created_by=created_by,
                reason=reason,
                supporting_document=supporting_document,
                signed_by=signed_by,
                signature=signature,
                created_at=_utcnow_iso(),
            )
        )
    return records


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ts_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


__all__ = [
    "BackOfficeLedgerService",
    "LedgerEntry",
    "LedgerSnapshot",
    "TaxLot",
    "AdjustmentRecord",
    "AdjustmentReceipt",
    "LedgerError",
    "LedgerPeriodError",
    "LedgerSourceMissing",
    "AdjustmentSignatureError",
    "LedgerExportError",
    "AuditAttachmentError",
    "parse_adjustments_markdown",
]
