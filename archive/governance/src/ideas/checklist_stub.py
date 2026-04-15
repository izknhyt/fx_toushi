"""Checklist generator stub for the Idea pipeline (see §3.26)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class StageChecklist:
    """Representation of a stage-specific checklist."""

    stage: str
    items: list[str] = field(default_factory=list)
    status: str = "todo"


class IdeaChecklistGeneratorStub:
    """Generates placeholder checklist items that always remain TODO."""

    _PLACEHOLDER = "TODO: governance checklist pending (M1 scaffold)"

    def generate(self, stage: str) -> StageChecklist:
        return StageChecklist(stage=stage, items=[f"{stage}: {self._PLACEHOLDER}"])
