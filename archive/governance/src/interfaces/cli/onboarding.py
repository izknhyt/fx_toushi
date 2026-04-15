"""Onboarding CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.docops.onboarding import OnboardingChecklistService, OnboardingError


def onboarding_assign(
    *,
    user_id: str,
    mentor_id: str,
    dry_run: bool = False,
    onboarding_path: Path = Path("docs/onboarding.md"),
    state_path: Path = Path("reports/governance/onboarding_assignments.json"),
    metrics_path: Path = Path("metrics/onboarding.jsonl"),
) -> Mapping[str, Any]:
    service = OnboardingChecklistService(
        onboarding_path=onboarding_path,
        state_path=state_path,
        metrics_path=metrics_path,
    )
    payload = service.assign(user_id=user_id, mentor_id=mentor_id, dry_run=dry_run)
    return payload


def onboarding_complete(
    *,
    user_id: str,
    task_slug: str,
    dry_run: bool = False,
    onboarding_path: Path = Path("docs/onboarding.md"),
    state_path: Path = Path("reports/governance/onboarding_assignments.json"),
    metrics_path: Path = Path("metrics/onboarding.jsonl"),
) -> Mapping[str, Any]:
    service = OnboardingChecklistService(
        onboarding_path=onboarding_path,
        state_path=state_path,
        metrics_path=metrics_path,
    )
    payload = service.complete(user_id=user_id, task_slug=task_slug, dry_run=dry_run)
    return payload


def onboarding_status(
    *,
    onboarding_path: Path = Path("docs/onboarding.md"),
    state_path: Path = Path("reports/governance/onboarding_assignments.json"),
    metrics_path: Path = Path("metrics/onboarding.jsonl"),
) -> Mapping[str, Any]:
    service = OnboardingChecklistService(
        onboarding_path=onboarding_path,
        state_path=state_path,
        metrics_path=metrics_path,
    )
    return service.status()


__all__ = ["onboarding_assign", "onboarding_complete", "onboarding_status", "OnboardingError"]
