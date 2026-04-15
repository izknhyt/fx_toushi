"""Release cutover CLI helpers."""

from __future__ import annotations

from pathlib import Path

from src.release.cutover import CutoverChecklistService


class CutoverBlockedError(RuntimeError):
    pass


def broker_cutover_generate(
    *,
    profile: str,
    version: str | None = None,
    base_dir: Path | None = None,
) -> dict[str, object]:
    service = CutoverChecklistService(base_dir=base_dir or Path("reports/audit/release"))
    checklist = service.generate(profile=profile, version=version)
    return {"status": "ok", **checklist.to_dict()}


def broker_cutover_verify(
    *,
    profile: str,
    version: str | None = None,
    base_dir: Path | None = None,
) -> dict[str, object]:
    service = CutoverChecklistService(base_dir=base_dir or Path("reports/audit/release"))
    payload = service.verify(profile=profile, version=version)
    if payload.get("status") != "ok":
        raise CutoverBlockedError("broker_cutover_pending")
    return payload


__all__ = ["broker_cutover_generate", "broker_cutover_verify", "CutoverBlockedError"]
