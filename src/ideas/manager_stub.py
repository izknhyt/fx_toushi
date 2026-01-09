"""Idea pipeline manager stubs as defined in detailed design §3.26."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IdeaManifestStub:
    """Minimal manifest representation returned by the M1 stub."""

    idea_id: str
    status: str = "not_applicable"
    stage: str = "draft"
    checklist_status: str = "todo"


@dataclass(slots=True)
class IdeaStageResult:
    """Result payload used by the stage transition stub."""

    accepted: bool
    reason: str
    next_stage: str | None = None


@dataclass(slots=True)
class IdeaEvidenceStatus:
    """Evidence validation result for the stub implementation."""

    not_assessed: bool = True
    issues: list[str] = field(default_factory=list)


class IdeaPipelineManagerStub:
    """No-op stand-in for the governance-backed Idea pipeline."""

    def load_manifest(self, idea_id: str) -> IdeaManifestStub:
        """Return a sentinel manifest without touching storage."""

        logger.info("ideas.manager.load_manifest noop (M1)", extra={"idea_id": idea_id})
        return IdeaManifestStub(idea_id=idea_id)

    def transition_stage(
        self, idea_id: str, target_stage: str, *, note: str | None = None
    ) -> IdeaStageResult:
        """Always deny stage transitions while governance is disabled."""

        logger.info(
            "ideas.manager.transition_stage noop (M1)",
            extra={"idea_id": idea_id, "target_stage": target_stage, "note": note},
        )
        return IdeaStageResult(accepted=False, reason="governance_disabled", next_stage=None)

    def validate_evidence(self, idea_id: str) -> IdeaEvidenceStatus:
        """Return Not Assessed so callers can short-circuit downstream workflows."""

        logger.info("ideas.manager.validate_evidence noop (M1)", extra={"idea_id": idea_id})
        return IdeaEvidenceStatus(not_assessed=True)
