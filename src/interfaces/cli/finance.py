"""Finance CLI helpers for backoffice ledger."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping
import os
import yaml

from src.backoffice.ledger import (
    BackOfficeLedgerService,
    LedgerPeriodError,
    LedgerSourceMissing,
    parse_adjustments_markdown,
    AdjustmentSignatureError,
)
from src.backoffice.tax_report import TaxReportGenerator, TaxReportError
from src.governance.secure_share import (
    SecureShareService,
    EvidenceDeliveryError,
    EvidenceEncryptionError,
    EvidenceManifestError,
    EvidenceScopeError,
)

DEFAULT_FEATURE_FLAGS = Path("config") / "feature_flags.yaml"


def generate_ledger(
    *,
    period: str,
    mode: str,
    include_pending: bool,
    profile: str | None = None,
    feature_flags_path: Path = DEFAULT_FEATURE_FLAGS,
) -> Mapping[str, Any]:
    if not _feature_enabled(
        flag="finance.backoffice_enabled", profile=profile, path=feature_flags_path
    ):
        return {"status": "disabled", "message": "Feature disabled (M2+)"}
    service = BackOfficeLedgerService()
    try:
        snapshot = service.generate(period=period, mode=mode, include_pending=include_pending)
    except LedgerPeriodError as exc:
        return {"status": "invalid", "reason": str(exc)}
    except LedgerSourceMissing as exc:
        return {"status": "pending", "reason": str(exc)}
    return {
        "status": "ok",
        "period": period,
        "mode": mode,
        "snapshot": asdict(snapshot),
    }


def _feature_enabled(*, path: Path, profile: str | None, flag: str) -> bool:
    if not path.exists():
        return False
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    defaults = payload.get("defaults") if isinstance(payload, dict) else None
    if not isinstance(defaults, dict):
        return False
    effective_profile = profile or os.getenv("TRADECTL_PROFILE", "live")
    profile_defaults = defaults.get(effective_profile)
    if not isinstance(profile_defaults, dict):
        return False
    return bool(profile_defaults.get(flag, False))


def generate_tax_report(
    *,
    year: int,
    mode: str,
    template: Path,
    jurisdiction: str,
    scenario: str,
    export_csv: bool,
    output_path: Path | None,
    profile: str | None = None,
    feature_flags_path: Path = DEFAULT_FEATURE_FLAGS,
) -> Mapping[str, Any]:
    if not _feature_enabled(
        flag="finance.backoffice_enabled", profile=profile, path=feature_flags_path
    ):
        return {"status": "disabled", "message": "Feature disabled (M2+)"}
    generator = TaxReportGenerator()
    try:
        result = generator.generate(
            year=year,
            mode=mode,
            template_path=template,
            jurisdiction=jurisdiction,
            scenario=scenario,
            export_csv=export_csv,
            output_path=output_path,
        )
    except TaxReportError as exc:
        return {"status": "error", "reason": str(exc)}
    return {
        "status": "ok",
        "year": year,
        "mode": mode,
        "markdown_path": result.markdown_path,
        "csv_path": result.csv_path,
        "json_path": result.json_path,
        "totals": result.totals,
    }


def ledger_diff(
    *,
    period_from: str,
    period_to: str,
    mode: str,
    profile: str | None = None,
    feature_flags_path: Path = DEFAULT_FEATURE_FLAGS,
) -> Mapping[str, Any]:
    if not _feature_enabled(
        flag="finance.backoffice_enabled", profile=profile, path=feature_flags_path
    ):
        return {"status": "disabled", "message": "Feature disabled (M2+)"}
    try:
        frame_from = _load_ledger_frame(period=period_from, mode=mode)
        frame_to = _load_ledger_frame(period=period_to, mode=mode)
    except LedgerSourceMissing as exc:
        return {"status": "pending", "reason": str(exc)}
    summary_from = _summarize_frame(frame_from)
    summary_to = _summarize_frame(frame_to)
    diff = {key: summary_to[key] - summary_from.get(key, 0.0) for key in summary_to}
    return {
        "status": "ok",
        "period_from": period_from,
        "period_to": period_to,
        "mode": mode,
        "summary_from": summary_from,
        "summary_to": summary_to,
        "diff": diff,
    }


def apply_adjustments(
    *,
    file_path: Path,
    period: str,
    mode: str,
    signer: str,
    profile: str | None = None,
    feature_flags_path: Path = DEFAULT_FEATURE_FLAGS,
) -> Mapping[str, Any]:
    if not _feature_enabled(
        flag="finance.backoffice_enabled", profile=profile, path=feature_flags_path
    ):
        return {"status": "disabled", "message": "Feature disabled (M2+)"}
    service = BackOfficeLedgerService()
    try:
        records = parse_adjustments_markdown(file_path, period=period, mode=mode)
        receipts = []
        for record in records:
            if not record.signed_by:
                record.signed_by = signer
            receipts.append(service.apply_adjustment(record))
    except (LedgerSourceMissing, AdjustmentSignatureError) as exc:
        return {"status": "error", "reason": str(exc)}
    return {
        "status": "ok",
        "count": len(receipts),
        "receipts": [asdict(receipt) for receipt in receipts],
    }


def share_evidence(
    *,
    profile_id: str,
    period: str,
    sources: str,
    channel: str,
    include_internal: bool,
    dry_run: bool,
    summary_only: bool,
    output_path: Path | None,
    profile: str | None = None,
    feature_flags_path: Path = DEFAULT_FEATURE_FLAGS,
) -> Mapping[str, Any]:
    if not _feature_enabled(
        flag="governance.secure_share_cli", profile=profile, path=feature_flags_path
    ):
        return {"status": "disabled", "message": "SecureShare disabled (M2+)"}
    service = SecureShareService()
    source_paths = _parse_sources(sources, period=period)
    try:
        package, manifest_path = service.prepare_package(
            profile_id=profile_id,
            period=period,
            sources=source_paths,
            include_internal=include_internal,
            created_by="cli",
        )
        if summary_only:
            summary_path = Path("reports") / "governance" / f"share_summary_{profile_id}_{period}.md"
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                "\n".join(
                    [
                        f"# Share Summary ({profile_id} {period})",
                        "",
                        f"- Package: {package.package_id}",
                        f"- Files: {len(package.files)}",
                        f"- Manifest: {manifest_path}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            return {"status": "ok", "summary_path": str(summary_path)}
        if dry_run:
            return {
                "status": "ok",
                "package_id": package.package_id,
                "manifest_path": str(manifest_path),
            }
        encrypted_path = service.encrypt_package(
            package=package,
            manifest_path=manifest_path,
            output_path=output_path,
        )
        record = service.publish(
            package=package,
            encrypted_path=encrypted_path,
            channel=channel,
        )
    except (
        EvidenceScopeError,
        EvidenceManifestError,
        EvidenceEncryptionError,
        EvidenceDeliveryError,
    ) as exc:
        return {"status": "error", "reason": str(exc)}
    return {
        "status": "ok",
        "package_id": record.package_id,
        "delivered_at": record.delivered_at,
        "channel": record.channel,
    }


def _load_ledger_frame(*, period: str, mode: str) -> Any:
    import pandas as pd

    parquet_path = Path("parquet") / "backoffice" / f"ledger_{mode}_{period}.parquet"
    if not parquet_path.exists():
        raise LedgerSourceMissing(f"ledger parquet missing: {parquet_path}")
    return pd.read_parquet(parquet_path)


def _summarize_frame(path_or_frame: Any) -> dict[str, float]:
    import pandas as pd

    frame = path_or_frame
    if isinstance(path_or_frame, Path):
        frame = pd.read_parquet(path_or_frame)
    return {
        "gross_pnl": float(frame["gross_pnl"].sum()) if "gross_pnl" in frame else 0.0,
        "fees": float(frame["fees"].sum()) if "fees" in frame else 0.0,
        "swap": float(frame["swap"].sum()) if "swap" in frame else 0.0,
    }


def _parse_sources(spec: str, *, period: str) -> list[Path]:
    sources: list[Path] = []
    for item in spec.split(","):
        token = item.strip()
        if not token:
            continue
        if ":" in token:
            kind, value = token.split(":", 1)
        else:
            kind, value = "path", token
        if kind == "audit":
            sources.append(Path("audit_pack") / value)
        elif kind == "ledger":
            sources.append(Path("parquet") / "backoffice" / f"ledger_{value}.parquet")
            sources.append(Path("jsonl") / "backoffice" / f"ledger_{value}.jsonl")
            mode = _parse_ledger_mode(value)
            if mode:
                sources.append(Path("reports") / "tax" / f"ledger_summary_{mode}_{period}.md")
            sources.append(Path("reports") / "tax" / f"ledger_summary_{period}.md")
        elif kind == "tax":
            sources.append(Path("reports") / "tax" / value)
        elif kind == "idea":
            sources.append(Path("research") / "ideas" / value / "evidence")
        elif kind == "path":
            sources.append(Path(value))
        else:
            sources.append(Path(value))
    return sources


def _parse_ledger_mode(value: str) -> str | None:
    if "_" not in value:
        return None
    parts = value.split("_")
    tail = parts[-1]
    if not tail.isdigit():
        return None
    return "_".join(parts[:-1]) if len(parts) > 1 else None


__all__ = [
    "generate_ledger",
    "generate_tax_report",
    "ledger_diff",
    "apply_adjustments",
    "share_evidence",
]
