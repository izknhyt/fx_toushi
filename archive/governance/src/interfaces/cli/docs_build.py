"""Docs build/lint/diff CLI helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Mapping

from tools.docbuild import DocBuildPipeline, MkDocsBuildError
from tools.doclint import DocLint, _collect_paths


class DocBuildCliError(Exception):
    """Raised when doc build CLI fails."""


def docs_build(
    *,
    clean: bool = False,
    strict: bool = False,
    dry_run: bool = False,
    serve: bool = False,
    dev_addr: str | None = None,
) -> Mapping[str, Any]:
    pipeline = DocBuildPipeline()
    try:
        if serve:
            result = pipeline.serve_site(dev_addr=dev_addr)
        else:
            result = pipeline.build_site(clean=clean, strict=strict, run_mkdocs=not dry_run)
    except MkDocsBuildError as exc:
        raise DocBuildCliError(str(exc)) from exc
    return {"status": "ok", "build": result.to_dict(), "dry_run": dry_run}


def docs_lint(
    *,
    category: str = "runbook",
    require_front_matter: bool = False,
) -> Mapping[str, Any]:
    paths = _collect_paths(category, root=Path("."))
    lint = DocLint(category=category, require_front_matter=require_front_matter)
    issues = lint.lint_paths(paths)
    return {
        "status": "ok" if not issues else "error",
        "issues": [issue.to_dict() for issue in issues],
    }


def docs_diff(*, against: str = "main") -> Mapping[str, Any]:
    command = ["git", "diff", "--name-only", against, "--", "docs", "reports"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise DocBuildCliError(result.stderr.strip() or "git diff failed")
    files = [line for line in result.stdout.splitlines() if line.strip()]
    report_path = Path("reports") / "governance" / f"doc_diff_{_today_stamp()}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_diff(files, against), encoding="utf-8")
    return {"status": "ok", "against": against, "files": files, "report_path": str(report_path)}


def _render_diff(files: list[str], against: str) -> str:
    lines = [f"# Doc Diff (against {against})", ""]
    if not files:
        lines.append("No doc changes detected.")
        return "\n".join(lines) + "\n"
    lines.append("## Changed files")
    lines.extend([f"- {path}" for path in files])
    return "\n".join(lines) + "\n"


def _today_stamp() -> str:
    from datetime import date

    return date.today().strftime("%Y%m%d")


__all__ = ["docs_build", "docs_lint", "docs_diff", "DocBuildCliError"]
