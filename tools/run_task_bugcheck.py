"""Run or plan bug-check bundles for the current codex_invest task."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCOPE_PATTERNS: dict[str, tuple[str, ...]] = {
    "portfolio_parity": (
        "src/strategies/",
        "src/interfaces/gui/",
        "tools/gui_ops_loop.py",
        "ui/web/",
        "src/portfolio/",
    ),
    "shadow_monitor": (
        "src/interfaces/gui/shadow_",
        "tools/render_daily_shadow",
        "tools/render_shadow_baseline_report.py",
    ),
    "ops_agenda": (
        "src/ops/agenda.py",
        "tests/unit/test_ops_agenda",
    ),
    "candidate_onboarding": (
        "tools/evaluate_portfolio_candidates.py",
        "tools/run_long_horizon_portfolio_validation.py",
        "tools/review_long_horizon_validation.py",
        "tools/run_allocator_tuning_review.py",
    ),
}

SCOPE_COMMANDS: dict[str, list[str]] = {
    "portfolio_parity": [
        "pytest -q tests/unit/test_strategy_allocation.py tests/integration/test_strategy_engine_allocation.py",
        "pytest -q tests/unit/test_gui_web_server.py tests/unit/test_gui_ops_loop.py tests/unit/test_shadow_gui_api.py",
    ],
    "shadow_monitor": [
        "pytest -q tests/unit/test_shadow_daily_alerts.py tests/unit/test_shadow_daily_history.py tests/unit/test_shadow_daily_review.py tests/unit/test_shadow_daily_ops.py tests/unit/test_shadow_gui_api.py tests/unit/test_gui_ops_loop.py",
    ],
    "ops_agenda": [
        "pytest -q tests/unit/test_ops_agenda_status.py tests/unit/test_ops_agenda_drills.py",
    ],
    "candidate_onboarding": [
        "pytest -q tests/unit/test_allocation_review.py tests/unit/test_review_long_horizon_validation.py tests/unit/test_evaluate_portfolio_candidates.py tests/unit/test_run_allocator_tuning_review.py",
    ],
}


def infer_scopes(changed_files: list[str]) -> list[str]:
    scopes: set[str] = set()
    for changed in changed_files:
        normalized = changed.replace("\\", "/")
        for scope, patterns in SCOPE_PATTERNS.items():
            if any(pattern in normalized for pattern in patterns):
                scopes.add(scope)
    if any(path.endswith(".py") for path in changed_files):
        scopes.add("python_compile")
    return sorted(scopes)


def build_bugcheck_plan(changed_files: list[str], explicit_scopes: list[str] | None = None) -> dict[str, Any]:
    scopes = sorted(set(explicit_scopes or []) | set(infer_scopes(changed_files)))
    commands: list[str] = []
    for scope in scopes:
        if scope == "python_compile":
            continue
        commands.extend(SCOPE_COMMANDS.get(scope, []))
    python_files = [path for path in changed_files if path.endswith(".py")]
    if python_files:
        quoted = " ".join(python_files)
        commands.append(f"python3 -m py_compile {quoted}")
    warnings: list[str] = []
    non_doc_changes = [path for path in changed_files if not path.startswith("docs/")]
    if non_doc_changes and "docs/development_plan.md" not in changed_files:
        warnings.append("development_plan_not_in_changed_files")
    if not scopes:
        warnings.append("no_scopes_inferred")
    return {
        "status": "ok",
        "scopes": scopes,
        "changed_files": changed_files,
        "commands": commands,
        "warnings": warnings,
    }


def run_bugcheck_plan(plan: dict[str, Any], *, workdir: Path) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    overall = "ok"
    for command in plan.get("commands", []):
        completed = subprocess.run(
            command,
            cwd=workdir,
            shell=True,
            text=True,
            capture_output=True,
        )
        results.append(
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "status": "ok" if completed.returncode == 0 else "failed",
            }
        )
        if completed.returncode != 0:
            overall = "failed"
    return {
        "status": overall,
        "scopes": plan.get("scopes", []),
        "warnings": plan.get("warnings", []),
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan or run bug-check bundles for a completed task.")
    parser.add_argument("--changed-file", action="append", default=[], help="Changed file path. Repeatable.")
    parser.add_argument(
        "--scope",
        action="append",
        default=[],
        choices=sorted(set(SCOPE_COMMANDS) | {"python_compile"}),
        help="Explicit bug-check scope. Repeatable.",
    )
    parser.add_argument("--output-json", type=Path, help="Optional JSON output path.")
    parser.add_argument("--run", action="store_true", help="Run the planned commands instead of only printing the plan.")
    args = parser.parse_args(argv)

    plan = build_bugcheck_plan(args.changed_file, explicit_scopes=args.scope)
    payload = run_bugcheck_plan(plan, workdir=PROJECT_ROOT) if args.run else plan
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload.get("status") != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
