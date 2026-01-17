"""Research idea CLI helpers."""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.ideas.manager import IdeaPipelineManager
from src.governance.secure_share import SecureShareService
from src.research.registry import (
    IdeaRegistry,
    StageIncompleteError,
    StageTransitionError,
)
from src.utils.hashing import sha256_path

DEFAULT_IDEA_ROOT = Path("research") / "ideas"
DEFAULT_IDEA_CONFIG = Path("config") / "idea_pipeline.yaml"
DEFAULT_FEATURE_FLAGS = Path("config") / "feature_flags.yaml"
DEFAULT_ROLES_PATH = Path("config") / "roles.yaml"

__all__ = [
    "list_ideas",
    "advance_stage",
    "checklist",
    "show_idea",
    "update_checklist",
    "evidence_bundle",
    "pipeline_report",
]


def list_ideas(
    *,
    stage: str | None = None,
    owner: str | None = None,
    root: Path = DEFAULT_IDEA_ROOT,
) -> Mapping[str, Any]:
    if not _idea_pipeline_enabled():
        return {"status": "disabled", "message": "Feature disabled (M2+)"}
    index_path = root / "index.yaml"
    if index_path.exists():
        manager = IdeaPipelineManager(
            root=root,
            config_path=DEFAULT_IDEA_CONFIG,
            feature_flags_path=DEFAULT_FEATURE_FLAGS,
            roles_path=DEFAULT_ROLES_PATH,
        )
        ideas = manager.load_registry()
        if stage:
            ideas = [idea for idea in ideas if idea.current_stage == stage]
        if owner:
            ideas = [idea for idea in ideas if idea.owner == owner]
        return {
            "status": "ok",
            "count": len(ideas),
            "ideas": [idea.to_dict() for idea in ideas],
            "source": "idea_pipeline",
        }
    registry = IdeaRegistry(root=root)
    ideas = registry.list(stage=stage, owner=owner)
    return {
        "status": "ok",
        "count": len(ideas),
        "ideas": [idea.to_dict() for idea in ideas],
        "source": "legacy_registry",
    }


def checklist(
    *,
    idea_id: str,
    stage: str | None = None,
    root: Path = DEFAULT_IDEA_ROOT,
) -> Mapping[str, Any]:
    if not _idea_pipeline_enabled():
        return {"status": "disabled", "message": "Feature disabled (M2+)"}
    index_path = root / "index.yaml"
    if index_path.exists():
        manager = IdeaPipelineManager(
            root=root,
            config_path=DEFAULT_IDEA_CONFIG,
            feature_flags_path=DEFAULT_FEATURE_FLAGS,
            roles_path=DEFAULT_ROLES_PATH,
        )
        result = manager.load_checklist(idea_id, stage)
        return {"status": "ok", "checklist": result.to_dict(), "source": "idea_pipeline"}
    registry = IdeaRegistry(root=root)
    result = registry.checklist(idea_id, stage=stage)
    return {"status": "ok", "checklist": result.to_dict(), "source": "legacy_registry"}


def advance_stage(
    *,
    idea_id: str,
    target_stage: str,
    note: str | None = None,
    actor: str | None = None,
    force: bool = False,
    root: Path = DEFAULT_IDEA_ROOT,
) -> Mapping[str, Any]:
    if not _idea_pipeline_enabled():
        return {"status": "disabled", "message": "Feature disabled (M2+)"}
    index_path = root / "index.yaml"
    if index_path.exists():
        manager = IdeaPipelineManager(
            root=root,
            config_path=DEFAULT_IDEA_CONFIG,
            feature_flags_path=DEFAULT_FEATURE_FLAGS,
            roles_path=DEFAULT_ROLES_PATH,
        )
        result = manager.transition_stage(
            idea_id,
            target_stage,
            actor=actor,
            note=note,
            force=force,
        )
        status = "ok" if result.allowed else "blocked"
        return {
            "status": status,
            "idea_id": idea_id,
            "from_stage": result.from_stage,
            "stage": target_stage,
            "reasons": result.reasons,
            "actions_required": result.actions_required,
            "source": "idea_pipeline",
        }
    registry = IdeaRegistry(root=root)
    try:
        checklist_result = registry.advance_stage(
            idea_id,
            target_stage=target_stage,
            note=note,
            actor=actor,
            force=force,
        )
    except StageIncompleteError as exc:
        return {
            "status": "incomplete",
            "idea_id": idea_id,
            "missing": list(exc.missing),
            "source": "legacy_registry",
        }
    except StageTransitionError as exc:
        return {"status": "invalid", "idea_id": idea_id, "reason": str(exc), "source": "legacy_registry"}
    return {
        "status": "ok",
        "idea_id": idea_id,
        "stage": target_stage,
        "checklist": checklist_result.to_dict(),
        "source": "legacy_registry",
    }


def show_idea(
    *,
    idea_id: str,
    root: Path = DEFAULT_IDEA_ROOT,
) -> Mapping[str, Any]:
    if not _idea_pipeline_enabled():
        return {"status": "disabled", "message": "Feature disabled (M2+)"}
    manager = IdeaPipelineManager(
        root=root,
        config_path=DEFAULT_IDEA_CONFIG,
        feature_flags_path=DEFAULT_FEATURE_FLAGS,
        roles_path=DEFAULT_ROLES_PATH,
    )
    record = manager.get_idea(idea_id)
    manifest = manager.load_manifest(idea_id)
    checklist = manager.load_checklist(idea_id, record.current_stage)
    return {
        "status": "ok",
        "idea": record.to_dict(),
        "manifest": manifest,
        "checklist": checklist.to_dict(),
    }


def update_checklist(
    *,
    idea_id: str,
    stage: str,
    item_id: str,
    status: str,
    evidence_path: Path | None = None,
    root: Path = DEFAULT_IDEA_ROOT,
) -> Mapping[str, Any]:
    if not _idea_pipeline_enabled():
        return {"status": "disabled", "message": "Feature disabled (M2+)"}
    manager = IdeaPipelineManager(
        root=root,
        config_path=DEFAULT_IDEA_CONFIG,
        feature_flags_path=DEFAULT_FEATURE_FLAGS,
        roles_path=DEFAULT_ROLES_PATH,
    )
    receipt = manager.record_checklist_progress(
        idea_id,
        stage=stage,
        item_id=item_id,
        status=status,
        evidence_path=evidence_path,
    )
    return {
        "status": "ok",
        "idea_id": receipt.idea_id,
        "stage": receipt.stage,
        "item_id": receipt.item_id,
        "item_status": receipt.status,
        "evidence_path": receipt.evidence_path,
        "updated_at": receipt.updated_at,
    }


def evidence_bundle(
    *,
    idea_id: str,
    stage: str,
    output_dir: Path,
    profile_id: str = "research_board",
    period: str | None = None,
    root: Path = DEFAULT_IDEA_ROOT,
) -> Mapping[str, Any]:
    if not _idea_pipeline_enabled():
        return {"status": "disabled", "message": "Feature disabled (M2+)"}
    manager = IdeaPipelineManager(
        root=root,
        config_path=DEFAULT_IDEA_CONFIG,
        feature_flags_path=DEFAULT_FEATURE_FLAGS,
        roles_path=DEFAULT_ROLES_PATH,
    )
    record = manager.get_idea(idea_id)
    definition = manager.get_stage_definition(stage)
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = output_dir / f"{idea_id}_{stage}_bundle.md"
    lines = [
        f"# Idea Evidence Bundle: {idea_id}",
        f"- Stage: {stage}",
        "",
        "## Evidence",
    ]
    missing: list[str] = []
    sources: list[Path] = []
    for spec in definition.required_evidence:
        path = Path(spec.path)
        if not path.is_absolute():
            path = record.path / spec.path
        if not path.exists():
            missing.append(spec.evidence_id)
            continue
        digest = sha256_path(path)
        lines.append(f"- {spec.evidence_id}: {path} ({digest})")
        sources.append(path)
    if missing:
        lines.append("")
        lines.append("## Missing")
        lines.extend([f"- {item}" for item in missing])
    bundle_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sources.append(bundle_path)
    effective_period = period or date.today().strftime("%G-W%V")
    share_service = SecureShareService()
    package = share_service.prepare_package(
        profile_id=profile_id,
        period=effective_period,
        sources=sources,
        include_internal=False,
        idea_id=idea_id,
    )
    return {
        "status": "ok",
        "idea_id": idea_id,
        "stage": stage,
        "bundle_path": str(bundle_path),
        "missing": missing,
        "share_manifest": str(package.manifest_path),
    }


def pipeline_report(
    *,
    week: str,
    output_dir: Path,
    root: Path = DEFAULT_IDEA_ROOT,
) -> Mapping[str, Any]:
    if not _idea_pipeline_enabled():
        return {"status": "disabled", "message": "Feature disabled (M2+)"}
    manager = IdeaPipelineManager(
        root=root,
        config_path=DEFAULT_IDEA_CONFIG,
        feature_flags_path=DEFAULT_FEATURE_FLAGS,
        roles_path=DEFAULT_ROLES_PATH,
    )
    path = manager.generate_pipeline_report(week=week, output_dir=output_dir)
    return {"status": "ok", "path": str(path)}


def _idea_pipeline_enabled() -> bool:
    if not DEFAULT_FEATURE_FLAGS.exists():
        return False
    try:
        payload = yaml.safe_load(DEFAULT_FEATURE_FLAGS.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    defaults = payload.get("defaults") if isinstance(payload, Mapping) else None
    if not isinstance(defaults, Mapping):
        return False
    profile = os.getenv("TRADECTL_PROFILE", "live")
    profile_defaults = defaults.get(profile)
    if not isinstance(profile_defaults, Mapping):
        return False
    return bool(profile_defaults.get("governance.idea_pipeline_enabled", False))
