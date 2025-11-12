from __future__ import annotations

from src.ideas import (
    IdeaChecklistGeneratorStub,
    IdeaChecklistValidatorStub,
    IdeaManifestStub,
    IdeaManifestValidatorStub,
    IdeaPipelineManagerStub,
)


def test_load_manifest_returns_stub() -> None:
    manager = IdeaPipelineManagerStub()
    manifest = manager.load_manifest("idea-001")
    assert isinstance(manifest, IdeaManifestStub)
    assert manifest.idea_id == "idea-001"
    assert manifest.status == "not_applicable"


def test_transition_stage_returns_blocked_result() -> None:
    manager = IdeaPipelineManagerStub()
    result = manager.transition_stage("idea-001", "paper")
    assert result.accepted is False
    assert result.reason == "governance_disabled"
    assert result.next_stage is None


def test_validate_evidence_marks_not_assessed() -> None:
    manager = IdeaPipelineManagerStub()
    status = manager.validate_evidence("idea-001")
    assert status.not_assessed is True
    assert status.issues == []


def test_schema_validators_always_pass() -> None:
    assert IdeaManifestValidatorStub().validate({"foo": "bar"})
    assert IdeaChecklistValidatorStub().validate(["task"])


def test_checklist_generator_keeps_items_in_todo_state() -> None:
    generator = IdeaChecklistGeneratorStub()
    checklist = generator.generate("paper")
    assert checklist.stage == "paper"
    assert checklist.status == "todo"
    assert checklist.items and "TODO" in checklist.items[0]
