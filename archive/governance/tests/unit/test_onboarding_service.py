from __future__ import annotations

from pathlib import Path

from src.docops.onboarding import OnboardingChecklistService


def _write_onboarding(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# Onboarding",
                "",
                "- [ ] Read runbook",
                "- [ ] Verify tooling",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_onboarding_assign_and_complete(tmp_path: Path) -> None:
    onboarding_path = tmp_path / "docs" / "onboarding.md"
    state_path = tmp_path / "reports" / "governance" / "onboarding_assignments.json"
    metrics_path = tmp_path / "metrics" / "onboarding.jsonl"
    report_dir = tmp_path / "reports" / "governance" / "onboarding"

    _write_onboarding(onboarding_path)
    service = OnboardingChecklistService(
        onboarding_path=onboarding_path,
        state_path=state_path,
        metrics_path=metrics_path,
        report_dir=report_dir,
    )

    payload = service.assign(user_id="u1", mentor_id="m1", dry_run=False)
    assert payload["status"] == "ok"

    slug = payload["assignment"]["tasks"][0]["slug"]
    payload = service.complete(user_id="u1", task_slug=slug, dry_run=True)
    assert payload["assignment"]["completion_pct"] > 0
