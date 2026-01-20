"""Research workspace manager for environment/data checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class WorkspaceStatus:
    status: str
    checked_at: str
    missing: list[str]
    warnings: list[str]
    workspace_root: str
    requirements_path: str
    config_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checked_at": self.checked_at,
            "missing": list(self.missing),
            "warnings": list(self.warnings),
            "workspace_root": self.workspace_root,
            "requirements_path": self.requirements_path,
            "config_path": self.config_path,
        }


class ResearchWorkspaceManager:
    def __init__(
        self,
        *,
        config_path: Path = Path("config") / "research_workspace.yaml",
        requirements_path: Path = Path("requirements-research.lock"),
    ) -> None:
        self._config_path = config_path
        self._requirements_path = requirements_path

    def check(self) -> WorkspaceStatus:
        config = self._load_config()
        missing: list[str] = []
        warnings: list[str] = []
        if not self._requirements_path.exists():
            missing.append(str(self._requirements_path))
        workspace_root = Path(config.get("workspace_root", "research_workspace"))
        if not workspace_root.exists():
            missing.append(str(workspace_root))
        for path in config.get("required_paths", []):
            if not Path(path).exists():
                missing.append(str(path))
        status = "ok" if not missing else "missing"
        return WorkspaceStatus(
            status=status,
            checked_at=_utcnow_iso(),
            missing=missing,
            warnings=warnings,
            workspace_root=str(workspace_root),
            requirements_path=str(self._requirements_path),
            config_path=str(self._config_path),
        )

    def sync(self) -> WorkspaceStatus:
        config = self._load_config()
        workspace_root = Path(config.get("workspace_root", "research_workspace"))
        workspace_root.mkdir(parents=True, exist_ok=True)
        for path in config.get("required_paths", []):
            Path(path).mkdir(parents=True, exist_ok=True)
        return self.check()

    def _load_config(self) -> dict[str, Any]:
        if not self._config_path.exists():
            return {"workspace_root": "research_workspace", "required_paths": []}
        payload = yaml.safe_load(self._config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            return {"workspace_root": "research_workspace", "required_paths": []}
        return payload


def main() -> int:
    manager = ResearchWorkspaceManager()
    status = manager.check()
    print(json.dumps(status.to_dict(), ensure_ascii=False, indent=2))
    return 0 if status.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
