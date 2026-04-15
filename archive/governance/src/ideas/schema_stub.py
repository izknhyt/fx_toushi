"""Schema validation scaffolds for Idea manifests/checklists."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence

logger = logging.getLogger(__name__)


class IdeaManifestValidatorStub:
    """Returns success without touching disk or schemas."""

    def validate(self, manifest: Mapping[str, object] | None = None) -> bool:
        logger.info(
            "ideas.schema.manifest noop (M1)",
            extra={"keys": sorted(manifest.keys()) if manifest else []},
        )
        return True


class IdeaChecklistValidatorStub:
    """Checklist validator stub that mirrors the manifest stub behaviour."""

    def validate(self, checklist: Sequence[str] | None = None) -> bool:
        logger.info(
            "ideas.schema.checklist noop (M1)", extra={"length": len(checklist) if checklist else 0}
        )
        return True
