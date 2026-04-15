"""Research workspace CLI helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tools.research_workspace import ResearchWorkspaceManager
from tools.run_notebook import NotebookRunner
from src.research.artifacts import ResearchArtifactRegistry


def workspace_status() -> Mapping[str, Any]:
    manager = ResearchWorkspaceManager()
    status = manager.check()
    return status.to_dict()


def workspace_sync() -> Mapping[str, Any]:
    manager = ResearchWorkspaceManager()
    status = manager.sync()
    return status.to_dict()


def run_notebook(
    *,
    path: Path,
    output_dir: Path | None,
    execute: bool,
) -> Mapping[str, Any]:
    runner = NotebookRunner()
    result = runner.run(notebook_path=path, output_dir=output_dir, execute=execute)
    return result.to_dict()


def artifact_add(
    *,
    path: Path,
    kind: str,
    name: str | None,
    owner: str | None,
    idea_id: str | None,
    playbook_id: str | None,
) -> Mapping[str, Any]:
    registry = ResearchArtifactRegistry()
    artifact = registry.register(
        path=path,
        kind=kind,
        name=name,
        owner=owner,
        idea_id=idea_id,
        playbook_id=playbook_id,
    )
    return {"status": "ok", "artifact": artifact.to_dict()}


def artifact_list() -> Mapping[str, Any]:
    registry = ResearchArtifactRegistry()
    artifacts = [artifact.to_dict() for artifact in registry.list()]
    return {"status": "ok", "count": len(artifacts), "artifacts": artifacts}


__all__ = ["workspace_status", "workspace_sync", "run_notebook", "artifact_add", "artifact_list"]
