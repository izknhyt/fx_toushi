from __future__ import annotations

from pathlib import Path

import pytest

from src.research.registry import IdeaRegistry, StageIncompleteError


def _write_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "idea_id: idea-001",
                "title: Mean Reversion",
                "owner: alice",
                "created_at: 2026-01-01T00:00:00Z",
                "hypothesis: Range-bound drift",
                "data_sources:",
                "  - dukascopy",
                "stage: draft",
                "checklists:",
                "  screening:",
                "    completed:",
                "      - data_sources",
                "    signoff: alice",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_idea_registry_list_and_checklist(tmp_path: Path) -> None:
    manifest_path = tmp_path / "ideas" / "idea-001" / "manifest.yaml"
    _write_manifest(manifest_path)
    registry = IdeaRegistry(root=tmp_path / "ideas")

    ideas = registry.list()
    assert len(ideas) == 1
    assert ideas[0].idea_id == "idea-001"

    checklist = registry.checklist("idea-001", stage="screening")
    assert "baseline_metrics" in checklist.missing()


def test_idea_stage_advance_requires_checklist(tmp_path: Path) -> None:
    manifest_path = tmp_path / "ideas" / "idea-001" / "manifest.yaml"
    _write_manifest(manifest_path)
    registry = IdeaRegistry(root=tmp_path / "ideas")

    with pytest.raises(StageIncompleteError):
        registry.advance_stage("idea-001", target_stage="screening")

    checklist = registry.advance_stage(
        "idea-001", target_stage="screening", force=True, note="test"
    )
    assert checklist.stage == "screening"

    report_path = registry.generate_report("idea-001", output_dir=tmp_path / "reports")
    assert report_path.exists()
