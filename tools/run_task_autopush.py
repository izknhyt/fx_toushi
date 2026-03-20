from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Iterable

DEFAULT_EXCLUDES = (
    "data/queues/bar_ready.jsonl",
    "reports/data_manifest.json",
)


def _run(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
    )


def parse_status_paths(status_output: str) -> list[str]:
    paths: list[str] = []
    for line in status_output.splitlines():
        if not line:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            paths.append(path)
    return paths


def filter_paths(paths: Iterable[str], excludes: Iterable[str]) -> list[str]:
    exclude_set = {item.strip() for item in excludes if item.strip()}
    return [path for path in paths if path not in exclude_set]


def build_bugcheck_command(
    *,
    repo_root: Path,
    changed_files: Iterable[str],
    scopes: Iterable[str],
) -> list[str]:
    command = [
        "python3",
        str(repo_root / "tools/run_task_bugcheck.py"),
    ]
    for scope in scopes:
        command.extend(["--scope", scope])
    for changed_file in changed_files:
        command.extend(["--changed-file", changed_file])
    command.append("--run")
    return command


def build_git_commands(
    *,
    paths: Iterable[str],
    message: str,
    remote: str,
    branch: str,
) -> list[list[str]]:
    normalized_paths = list(paths)
    return [
        ["git", "add", "--", *normalized_paths],
        ["git", "commit", "-m", message],
        ["git", "push", remote, branch],
    ]


def detect_branch(repo_root: Path) -> str:
    result = _run(["git", "branch", "--show-current"], cwd=repo_root)
    return result.stdout.strip()


def collect_changed_paths(repo_root: Path) -> list[str]:
    result = _run(["git", "status", "--short"], cwd=repo_root)
    return parse_status_paths(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run task bugcheck, stage commit-scope changes, commit, and push."
    )
    parser.add_argument("--message", required=True, help="Commit message.")
    parser.add_argument("--remote", default="origin", help="Git remote to push to.")
    parser.add_argument("--branch", help="Branch to push. Defaults to current branch.")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Path to exclude from staging. May be passed multiple times.",
    )
    parser.add_argument(
        "--scope",
        action="append",
        default=[],
        help="Explicit bugcheck scope. May be passed multiple times.",
    )
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Explicit changed file for bugcheck runner. May be passed multiple times.",
    )
    parser.add_argument(
        "--skip-bugcheck",
        action="store_true",
        help="Skip task bugcheck before staging/commit/push.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute the planned commands. Without this flag, print the plan only.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    branch = args.branch or detect_branch(repo_root)
    status_paths = collect_changed_paths(repo_root)
    excludes = list(DEFAULT_EXCLUDES) + list(args.exclude)
    changed_paths = filter_paths(status_paths, excludes)
    bugcheck_files = list(args.changed_file) or changed_paths

    summary: dict[str, object] = {
        "status": "planned",
        "branch": branch,
        "remote": args.remote,
        "excluded_paths": excludes,
        "status_paths": status_paths,
        "changed_paths": changed_paths,
        "bugcheck_files": bugcheck_files,
    }

    if not changed_paths:
        summary["status"] = "no_changes"
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    commands: list[list[str]] = []
    if not args.skip_bugcheck:
        commands.append(
            build_bugcheck_command(
                repo_root=repo_root,
                changed_files=bugcheck_files,
                scopes=args.scope,
            )
        )
    commands.extend(
        build_git_commands(
            paths=changed_paths,
            message=args.message,
            remote=args.remote,
            branch=branch,
        )
    )
    summary["commands"] = [" ".join(command) for command in commands]

    if not args.run:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    results: list[dict[str, object]] = []
    for command in commands:
        completed = _run(command, cwd=repo_root)
        results.append(
            {
                "command": " ".join(command),
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "returncode": completed.returncode,
            }
        )

    summary["status"] = "ok"
    summary["results"] = results
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
