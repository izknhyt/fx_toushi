from __future__ import annotations

from pathlib import Path

from tools.research_workspace import ResearchWorkspaceManager


def test_research_workspace_manager_sync_and_check(tmp_path: Path) -> None:
    config_path = tmp_path / "research_workspace.yaml"
    workspace_root = tmp_path / "workspace"
    config_path.write_text(
        "schema_version: research_workspace.v1\n"
        f"workspace_root: \"{workspace_root}\"\n"
        "required_paths:\n"
        f"  - \"{workspace_root / 'notebooks'}\"\n"
        f"  - \"{tmp_path / 'reports' / 'research'}\"\n",
        encoding="utf-8",
    )
    requirements_path = tmp_path / "requirements-research.lock"
    requirements_path.write_text("nbformat==5.9.2\n", encoding="utf-8")

    manager = ResearchWorkspaceManager(
        config_path=config_path, requirements_path=requirements_path
    )
    status = manager.sync()
    assert status.status == "ok"
    assert status.missing == []
    assert workspace_root.exists()
