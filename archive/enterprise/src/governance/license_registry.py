"""License registry service for market data providers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.utils.hashing import sha256_path

DEFAULT_LICENSE_REGISTRY = Path("reports/governance/licensing/license_registry.yaml")
DEFAULT_LICENSE_METRICS = Path("metrics/licensing.jsonl")
DEFAULT_USAGE_HISTORY = Path("reports/governance/licensing/usage_history.jsonl")


class LicenseSchemaError(RuntimeError):
    """Raised when the license registry schema is invalid."""


class LicenseNotFound(RuntimeError):
    """Raised when a provider license record is missing."""


class HashMismatchError(RuntimeError):
    """Raised when a contract hash validation fails."""


@dataclass(slots=True)
class LicenseDocument:
    kind: str
    path: str
    hash_sha256: str
    added_at: str
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "path": self.path,
            "hash_sha256": self.hash_sha256,
            "added_at": self.added_at,
            "notes": self.notes,
        }


@dataclass(slots=True)
class LicenseRecord:
    provider_id: str
    contract_id: str
    effective_from: str
    effective_to: str
    cost_plan: str
    rate_limit_terms: str
    redistribution_rules: str
    usage_scope: str
    contact: str
    status: str
    documents: list[LicenseDocument] = field(default_factory=list)
    last_review_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "contract_id": self.contract_id,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "cost_plan": self.cost_plan,
            "rate_limit_terms": self.rate_limit_terms,
            "redistribution_rules": self.redistribution_rules,
            "usage_scope": self.usage_scope,
            "contact": self.contact,
            "status": self.status,
            "documents": [doc.to_dict() for doc in self.documents],
            "last_review_at": self.last_review_at,
        }


@dataclass(slots=True)
class LicenseRegistry:
    schema_version: str
    records: list[LicenseRecord]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "records": [record.to_dict() for record in self.records],
        }


class LicenseRegistryService:
    def __init__(
        self,
        *,
        path: Path = DEFAULT_LICENSE_REGISTRY,
        metrics_path: Path = DEFAULT_LICENSE_METRICS,
        usage_history_path: Path = DEFAULT_USAGE_HISTORY,
    ) -> None:
        self._path = path
        self._metrics_path = metrics_path
        self._usage_history_path = usage_history_path
        self._registry = self._load()

    def _load(self) -> LicenseRegistry:
        if not self._path.exists():
            return LicenseRegistry(schema_version="license_registry.v1", records=[])
        payload = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, Mapping):
            raise LicenseSchemaError("license registry payload invalid")
        records_payload = payload.get("records", [])
        if not isinstance(records_payload, list):
            raise LicenseSchemaError("license registry records invalid")
        records: list[LicenseRecord] = []
        for entry in records_payload:
            if not isinstance(entry, Mapping):
                continue
            provider_id = str(entry.get("provider_id") or "")
            contract_id = str(entry.get("contract_id") or "")
            if not provider_id or not contract_id:
                raise LicenseSchemaError("provider_id/contract_id required")
            documents = []
            for doc in entry.get("documents", []) or []:
                if not isinstance(doc, Mapping):
                    continue
                documents.append(
                    LicenseDocument(
                        kind=str(doc.get("kind") or "unknown"),
                        path=str(doc.get("path") or ""),
                        hash_sha256=str(doc.get("hash_sha256") or ""),
                        added_at=str(doc.get("added_at") or _utcnow_iso()),
                        notes=doc.get("notes"),
                    )
                )
            records.append(
                LicenseRecord(
                    provider_id=provider_id,
                    contract_id=contract_id,
                    effective_from=str(entry.get("effective_from") or ""),
                    effective_to=str(entry.get("effective_to") or ""),
                    cost_plan=str(entry.get("cost_plan") or ""),
                    rate_limit_terms=str(entry.get("rate_limit_terms") or ""),
                    redistribution_rules=str(entry.get("redistribution_rules") or ""),
                    usage_scope=str(entry.get("usage_scope") or ""),
                    contact=str(entry.get("contact") or ""),
                    status=str(entry.get("status") or "provisional"),
                    documents=documents,
                    last_review_at=str(entry.get("last_review_at") or "")
                    if entry.get("last_review_at")
                    else None,
                )
            )
        return LicenseRegistry(
            schema_version=str(payload.get("schema_version") or "license_registry.v1"),
            records=records,
        )

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._registry.to_dict()
        if _yaml_dump(self._path, payload):
            return
        self._path.write_text(
            "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_records(self) -> list[LicenseRecord]:
        return list(self._registry.records)

    def get(self, provider_id: str) -> LicenseRecord:
        record = next(
            (record for record in self._registry.records if record.provider_id == provider_id),
            None,
        )
        if not record:
            raise LicenseNotFound(provider_id)
        return record

    def attach_contract(self, provider_id: str, pdf_path: Path) -> LicenseRecord:
        if not pdf_path.exists():
            raise FileNotFoundError(str(pdf_path))
        record = self.get(provider_id)
        digest = sha256_path(pdf_path)
        record.documents.append(
            LicenseDocument(
                kind="contract_pdf",
                path=str(pdf_path),
                hash_sha256=digest,
                added_at=_utcnow_iso(),
            )
        )
        self._append_metrics(
            {
                "event": "license.contract_attached",
                "provider_id": provider_id,
                "hash_sha256": digest,
            }
        )
        self.save()
        return record

    def record_usage(self, provider_id: str, metrics_snapshot: Mapping[str, Any]) -> None:
        record = self.get(provider_id)
        cost_per_hour = float(metrics_snapshot.get("cost_per_hour_jpy") or 0.0)
        usage = {
            "ts": _utcnow_iso(),
            "provider_id": provider_id,
            "cost_per_hour_jpy": cost_per_hour,
            "cost_estimate_monthly_jpy": cost_per_hour * 24 * 30,
            "rate_limit_hits": int(metrics_snapshot.get("rate_limit_hits") or 0),
        }
        self._append_jsonl(self._usage_history_path, usage)
        self._append_metrics(
            {
                "event": "license.usage_recorded",
                "provider_id": provider_id,
                "estimated_monthly_cost_jpy": usage["cost_estimate_monthly_jpy"],
            }
        )
        record.status = record.status or "active"
        self.save()

    def compliance_status(self, provider_id: str) -> str:
        record = self.get(provider_id)
        if record.status not in {"active", "provisional"}:
            return record.status
        if not record.documents:
            return "provisional"
        if record.effective_to:
            try:
                expiry = _parse_date(record.effective_to)
                if expiry <= datetime.now(timezone.utc):
                    return "expired"
            except ValueError:
                return "provisional"
        return record.status or "provisional"

    def next_review_due(self, provider_id: str) -> str | None:
        record = self.get(provider_id)
        if not record.effective_to:
            return None
        try:
            expiry = _parse_date(record.effective_to)
        except ValueError:
            return None
        due = expiry - timedelta(days=90)
        return due.date().isoformat()

    def ensure_precheck(self, provider_id: str) -> None:
        status = self.compliance_status(provider_id)
        if status not in {"active", "provisional"}:
            raise LicenseSchemaError(f"license status {status} for {provider_id}")
        if status == "provisional":
            raise LicenseSchemaError("license evidence incomplete")

    def generate_summary(self, provider_id: str) -> Path:
        record = self.get(provider_id)
        output_dir = DEFAULT_LICENSE_REGISTRY.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{provider_id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.md"
        lines = [
            "# License Summary",
            f"- provider_id: {record.provider_id}",
            f"- contract_id: {record.contract_id}",
            f"- effective_from: {record.effective_from}",
            f"- effective_to: {record.effective_to}",
            f"- status: {record.status}",
            f"- next_review_due: {self.next_review_due(provider_id)}",
            "",
            "## Usage Scope",
            record.usage_scope,
            "",
            "## Documents",
        ]
        if record.documents:
            for doc in record.documents:
                lines.append(f"- {doc.kind}: {doc.path} ({doc.hash_sha256})")
        else:
            lines.append("- none")
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output_path

    def _append_metrics(self, payload: Mapping[str, object]) -> None:
        self._append_jsonl(
            self._metrics_path,
            {"ts": _utcnow_iso(), **payload},
        )

    def _append_jsonl(self, path: Path, payload: Mapping[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _yaml_dump(path: Path, payload: dict[str, object]) -> bool:
    if not hasattr(yaml, "safe_dump"):
        return False
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return True


def _parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "LicenseRegistryService",
    "LicenseRecord",
    "LicenseDocument",
    "LicenseRegistry",
    "LicenseSchemaError",
    "LicenseNotFound",
    "HashMismatchError",
]
