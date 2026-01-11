"""Paid feed capability registry and licensing evaluation."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

DEFAULT_CAPABILITIES_PATH = Path("config/provider_capabilities.yaml")
DEFAULT_EVIDENCE_DIR = Path("reports/governance/licensing")
DEFAULT_METRICS_PATH = Path("metrics/paid_feed_evaluation.jsonl")


@dataclass(slots=True)
class ProviderCapability:
    provider: str
    paid_feed: bool
    license_required: bool
    notes: str | None = None


class ProviderCapabilityRegistry:
    def __init__(self, *, path: Path = DEFAULT_CAPABILITIES_PATH) -> None:
        self._path = path
        self._cache: dict[str, ProviderCapability] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._cache = {
                "yfinance": ProviderCapability(
                    provider="yfinance",
                    paid_feed=False,
                    license_required=False,
                    notes="community",
                ),
                "dukascopy": ProviderCapability(
                    provider="dukascopy",
                    paid_feed=False,
                    license_required=False,
                    notes="public",
                ),
                "paid_feed_stub": ProviderCapability(
                    provider="paid_feed_stub",
                    paid_feed=True,
                    license_required=True,
                    notes="stub",
                ),
            }
            return
        payload = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        raw = payload.get("providers") if isinstance(payload, dict) else payload
        if not isinstance(raw, Mapping):
            return
        for name, entry in raw.items():
            if not isinstance(entry, Mapping):
                continue
            self._cache[str(name)] = ProviderCapability(
                provider=str(name),
                paid_feed=bool(entry.get("paid_feed", False)),
                license_required=bool(entry.get("license_required", False)),
                notes=str(entry.get("notes")) if entry.get("notes") else None,
            )

    def get(self, provider: str) -> ProviderCapability:
        return self._cache.get(provider) or ProviderCapability(
            provider=provider,
            paid_feed=False,
            license_required=False,
            notes="unknown",
        )


@dataclass(slots=True)
class PaidFeedEvaluationResult:
    status: str
    provider: str
    paid_feed_enabled: bool
    license_required: bool
    evidence_paths: list[str]
    reason: str | None
    ts: str

    def to_dict(self) -> dict[str, object]:
        return {
            "ts": self.ts,
            "status": self.status,
            "provider": self.provider,
            "paid_feed_enabled": self.paid_feed_enabled,
            "license_required": self.license_required,
            "evidence_paths": list(self.evidence_paths),
            "reason": self.reason,
        }


class PaidFeedEvaluator:
    def __init__(
        self,
        *,
        registry: ProviderCapabilityRegistry | None = None,
        metrics_path: Path = DEFAULT_METRICS_PATH,
    ) -> None:
        self._registry = registry or ProviderCapabilityRegistry()
        self._metrics_path = metrics_path

    def evaluate(
        self,
        *,
        profile: str | None = None,
        provider: str | None = None,
        evidence_dir: Path = DEFAULT_EVIDENCE_DIR,
        write_report: bool = False,
        report_path: Path | None = None,
    ) -> PaidFeedEvaluationResult:
        profile = profile or os.getenv("TRADECTL_PROFILE")
        paid_feed_enabled = _read_feature_flag("data.paid_feed", profile=profile)
        provider = provider or os.getenv("TRADECTL_PAID_FEED_PROVIDER") or "paid_feed_stub"
        capability = self._registry.get(provider)
        evidence_paths = _find_evidence_paths(evidence_dir)

        status = "disabled"
        reason = None
        if paid_feed_enabled:
            if not capability.paid_feed:
                status = "mismatch"
                reason = "provider_not_paid"
            elif capability.license_required and not evidence_paths:
                status = "blocked"
                reason = "license_evidence_missing"
            else:
                status = "ok"

        result = PaidFeedEvaluationResult(
            status=status,
            provider=provider,
            paid_feed_enabled=paid_feed_enabled,
            license_required=capability.license_required,
            evidence_paths=[str(path) for path in evidence_paths],
            reason=reason,
            ts=_utcnow_iso(),
        )
        _append_jsonl(self._metrics_path, result.to_dict())
        if write_report:
            resolved_report = report_path or _default_report_path(evidence_dir)
            _write_report(resolved_report, result)
        return result


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _default_report_path(evidence_dir: Path) -> Path:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    return evidence_dir / f"paid_feed_{ts}.md"


def _write_report(path: Path, result: PaidFeedEvaluationResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Paid Feed Licensing Report",
        f"- generated_at: {result.ts}",
        f"- status: {result.status}",
        f"- provider: {result.provider}",
        f"- paid_feed_enabled: {result.paid_feed_enabled}",
        f"- license_required: {result.license_required}",
    ]
    if result.reason:
        lines.append(f"- reason: {result.reason}")
    lines.append("- evidence_paths:")
    if result.evidence_paths:
        for entry in result.evidence_paths:
            lines.append(f"  - {entry}")
    else:
        lines.append("  - none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _find_evidence_paths(evidence_dir: Path) -> list[Path]:
    if not evidence_dir.exists():
        return []
    patterns = ["paid_feed_*", "license_*", "contract_*"]
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(sorted(evidence_dir.glob(pattern)))
    return paths


def _read_feature_flag(
    flag: str,
    *,
    profile: str | None,
    path: Path = Path("config/feature_flags.yaml"),
) -> bool:
    if not profile:
        return False
    if not path.exists():
        return False
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    defaults = payload.get("defaults") or {}
    profile_defaults = defaults.get(profile)
    if not isinstance(profile_defaults, Mapping):
        return False
    return bool(profile_defaults.get(flag, False))


__all__ = [
    "ProviderCapability",
    "ProviderCapabilityRegistry",
    "PaidFeedEvaluationResult",
    "PaidFeedEvaluator",
    "DEFAULT_CAPABILITIES_PATH",
    "DEFAULT_EVIDENCE_DIR",
    "DEFAULT_METRICS_PATH",
]
