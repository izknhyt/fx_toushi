"""Ensure code changes are paired with documentation updates as per §0.6.11/§12.3."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DOC_PATHS = (
    "detailed_design_fx_signal_tool_v1.md",
    "docs/runbooks/",
    "docs/change_requests/",
    "docs/review_log.md",
    "docs/implementation_packets/",
    "docs/prompt_packages/",
    "docs/validation/",
)

CODE_PATHS = (
    "src/",
    "tests/",
    "tools/",
    "tradectl/",
    "config/",
    "ci/",
    "Makefile",
    "pyproject.toml",
    "poetry.lock",
    "reports/",
    "metrics/",
    "data/",
)


def _run_git_status() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _run_git_diff(compare_ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{compare_ref}...HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git diff against {compare_ref} failed")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _extract_path(entry: str) -> str:
    # format: "XY path"
    return entry[3:].strip()


def _matches(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in prefixes)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fail if code changes are not paired with doc/runbook updates."
    )
    parser.add_argument("--verbose", action="store_true", help="Print matched paths for debugging")
    parser.add_argument(
        "--compare-ref",
        type=str,
        default=None,
        help="Git ref to diff against (e.g. origin/main). When provided, git diff --name-only <ref>...HEAD is used.",
    )
    args = parser.parse_args()

    if args.compare_ref:
        entries = _run_git_diff(args.compare_ref)
        # git diff only returns file paths, so wrap to mimic status entries
        entries = [f"?? {path}" for path in entries]
    else:
        entries = _run_git_status()

    if not entries:
        if args.verbose:
            print("[doc-sync] clean working tree")
        sys.exit(0)

    code_paths: list[str] = []
    doc_paths: list[str] = []
    for entry in entries:
        path = _extract_path(entry)
        if _matches(path, DOC_PATHS):
            doc_paths.append(path)
        if _matches(path, CODE_PATHS):
            code_paths.append(path)

    if args.verbose:
        print(f"[doc-sync] code paths: {code_paths or 'n/a'}")
        print(f"[doc-sync] doc paths: {doc_paths or 'n/a'}")

    if code_paths and not doc_paths:
        print(
            "Detected source changes without any Runbook/design/CR updates.\n"
            "Update `detailed_design_fx_signal_tool_v1.md`, `docs/runbooks/`, or "
            "`docs/change_requests/` (or record a TODO per RUN-POST-03) before opening a PR.",
            file=sys.stderr,
        )
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
