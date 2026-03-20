from __future__ import annotations

from pathlib import Path

from tools.run_task_autopush import (
    build_bugcheck_command,
    build_git_commands,
    filter_paths,
    parse_status_paths,
)


def test_parse_status_paths_handles_modified_and_rename() -> None:
    output = " M docs/development_plan.md\nR  old.py -> new.py\n?? tests/unit/test_x.py\n"
    assert parse_status_paths(output) == [
        "docs/development_plan.md",
        "new.py",
        "tests/unit/test_x.py",
    ]


def test_filter_paths_excludes_runtime_state() -> None:
    paths = [
        "docs/development_plan.md",
        "data/queues/bar_ready.jsonl",
        "reports/data_manifest.json",
        "src/portfolio/shadow_feedback.py",
    ]
    assert filter_paths(paths, ["data/queues/bar_ready.jsonl", "reports/data_manifest.json"]) == [
        "docs/development_plan.md",
        "src/portfolio/shadow_feedback.py",
    ]


def test_build_bugcheck_command_and_git_commands() -> None:
    repo_root = Path("/tmp/repo")
    bugcheck = build_bugcheck_command(
        repo_root=repo_root,
        changed_files=["src/x.py", "docs/development_plan.md"],
        scopes=["portfolio_parity", "python_compile"],
    )
    assert bugcheck == [
        "python3",
        "/tmp/repo/tools/run_task_bugcheck.py",
        "--scope",
        "portfolio_parity",
        "--scope",
        "python_compile",
        "--changed-file",
        "src/x.py",
        "--changed-file",
        "docs/development_plan.md",
        "--run",
    ]

    commands = build_git_commands(
        paths=["src/x.py", "docs/development_plan.md"],
        message="Test commit",
        remote="origin",
        branch="main",
    )
    assert commands == [
        ["git", "add", "--", "src/x.py", "docs/development_plan.md"],
        ["git", "commit", "-m", "Test commit"],
        ["git", "push", "origin", "main"],
    ]
