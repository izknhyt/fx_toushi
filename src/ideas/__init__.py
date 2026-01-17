"""Idea Pipeline scaffolds for the M1 release."""

from .checklist_stub import IdeaChecklistGeneratorStub, StageChecklist
from .manager import (
    ChecklistIncompleteError,
    EvidenceMissingError,
    IdeaNotFoundError,
    IdeaPipelineManager,
    IdeaPipelineError,
    MetricsGapError,
    StageDefinitionMissing,
    StageEvaluationResult,
)
from .manager_stub import (
    IdeaEvidenceStatus,
    IdeaManifestStub,
    IdeaPipelineManagerStub,
    IdeaStageResult,
)
from .schema_stub import IdeaChecklistValidatorStub, IdeaManifestValidatorStub

__all__ = [
    "IdeaPipelineManager",
    "IdeaPipelineError",
    "IdeaNotFoundError",
    "StageDefinitionMissing",
    "ChecklistIncompleteError",
    "EvidenceMissingError",
    "MetricsGapError",
    "StageEvaluationResult",
    "IdeaEvidenceStatus",
    "IdeaManifestStub",
    "IdeaPipelineManagerStub",
    "IdeaStageResult",
    "IdeaManifestValidatorStub",
    "IdeaChecklistValidatorStub",
    "IdeaChecklistGeneratorStub",
    "StageChecklist",
]
