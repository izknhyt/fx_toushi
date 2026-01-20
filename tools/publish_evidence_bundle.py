#!/usr/bin/env python3
"""Publish secure share evidence bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.governance.secure_share import (
    SecureShareService,
    EvidenceDeliveryError,
    EvidenceEncryptionError,
    EvidenceManifestError,
    EvidenceScopeError,
)


def _parse_sources(spec: str, period: str) -> list[Path]:
    sources: list[Path] = []
    if not spec:
        return sources
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
            sources.append(Path("reports") / "tax" / f"ledger_summary_{period}.md")
        elif kind == "tax":
            year = value
            sources.append(Path("reports") / "tax" / year)
        elif kind == "idea":
            sources.append(Path("research") / "ideas" / value / "evidence")
        elif kind == "path":
            sources.append(Path(value))
        else:
            sources.append(Path(value))
    return sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish secure share evidence bundles.")
    parser.add_argument("--profile", required=True, help="Share profile id")
    parser.add_argument("--period", required=True, help="Reporting period")
    parser.add_argument("--sources", required=True, help="Source list (kind:value,comma-separated)")
    parser.add_argument("--include-internal", action="store_true", help="Include internal files")
    parser.add_argument("--channel", default="local", help="Delivery channel")
    parser.add_argument("--out", default=None, help="Encrypted output path")
    parser.add_argument("--dry-run", action="store_true", help="Prepare only")
    parser.add_argument("--summary-only", action="store_true", help="Write share summary only")
    args = parser.parse_args()

    service = SecureShareService()
    sources = _parse_sources(args.sources, args.period)
    try:
        package, manifest_path = service.prepare_package(
            profile_id=args.profile,
            period=args.period,
            sources=sources,
            include_internal=args.include_internal,
            created_by="cli",
        )
        if args.summary_only:
            summary_path = Path("reports") / "governance" / f"share_summary_{args.profile}_{args.period}.md"
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                "\n".join(
                    [
                        f"# Share Summary ({args.profile} {args.period})",
                        "",
                        f"- Package: {package.package_id}",
                        f"- Files: {len(package.files)}",
                        f"- Manifest: {manifest_path}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            print(json.dumps({"status": "ok", "summary_path": str(summary_path)}, ensure_ascii=False))
            return 0
        if args.dry_run:
            print(
                json.dumps(
                    {"status": "ok", "package_id": package.package_id, "manifest": str(manifest_path)},
                    ensure_ascii=False,
                )
            )
            return 0
        encrypted = service.encrypt_package(
            package=package,
            manifest_path=manifest_path,
            output_path=Path(args.out) if args.out else None,
        )
        record = service.publish(
            package=package,
            encrypted_path=encrypted,
            channel=args.channel,
        )
    except (
        EvidenceScopeError,
        EvidenceManifestError,
        EvidenceEncryptionError,
        EvidenceDeliveryError,
    ) as exc:
        print(f"[secure-share] {exc}")
        return 1
    payload = {
        "status": record.status,
        "package_id": record.package_id,
        "channel": record.channel,
        "delivered_at": record.delivered_at,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
