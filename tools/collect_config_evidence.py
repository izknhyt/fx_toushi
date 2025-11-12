"""Generate or verify CONFIG-SCAFF-01 evidence bundles."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports" / "validation_log"


def _poetry_available() -> bool:
    return shutil.which("poetry") is not None


def _run_command(cmd: list[str], *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command {' '.join(cmd)} failed with code {result.returncode}:\n{result.stdout}\n{result.stderr}"
        )
    return result.stdout + result.stderr


def _schema_validate() -> str:
    if _poetry_available():
        cmd = [
            "poetry",
            "run",
            "schema-validate",
            "config",
            "--schema",
            "docs/schemas/config_bundle.schema.json",
        ]
        return _run_command(cmd)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    cmd = [
        sys.executable,
        "-m",
        "src.interfaces.cli.schema_validate",
        "config",
        "--schema",
        "docs/schemas/config_bundle.schema.json",
    ]
    return _run_command(cmd, env=env)


def _pytest_config_smoke() -> str:
    if _poetry_available():
        cmd = ["poetry", "run", "pytest", "-k", "config_schema_smoke"]
    else:
        cmd = [sys.executable, "-m", "pytest", "-k", "config_schema_smoke"]
    return _run_command(cmd)


def _config_init(*, dry_run: bool) -> str:
    cmd = [sys.executable, "tools/scripts/config_init.py"]
    if dry_run:
        cmd.append("--dry-run")
    if _poetry_available():
        cmd = ["poetry", "run"] + cmd
    return _run_command(cmd)


def generate_evidence(*, overwrite: bool) -> Path:
    timestamp = datetime.now(timezone.utc).astimezone()
    report_path = REPORTS_DIR / f"config_init_{timestamp:%Y%m%d}.md"
    if report_path.exists() and not overwrite:
        raise RuntimeError(f"{report_path} already exists. Use --overwrite to regenerate.")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    sections = [
        ("Config Init (dry-run)", _config_init(dry_run=True)),
        ("Config Init (apply)", _config_init(dry_run=False)),
        ("Schema Validate", _schema_validate()),
        ("pytest -k config_schema_smoke", _pytest_config_smoke()),
    ]

    lines = [
        f"# CONFIG-SCAFF-01 Evidence — {timestamp:%Y-%m-%d}",
        "",
        f"- Generated: {timestamp.isoformat()}",
        "",
    ]
    for title, log in sections:
        lines.append(f"## {title}")
        lines.append("```")
        lines.append(log.strip() or "(no output)")
        lines.append("```")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def verify_latest(grace_days: int) -> Path:
    today = datetime.now(timezone.utc).astimezone().date()
    for offset in range(grace_days + 1):
        current = today - timedelta(days=offset)
        candidate = REPORTS_DIR / f"config_init_{current:%Y%m%d}.md"
        if candidate.exists():
            return candidate
    raise RuntimeError(
        f"No config_init_<date>.md found within {grace_days} day(s). "
        "Run `make config-evidence` and commit the evidence bundle."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate or verify CONFIG-SCAFF-01 evidence.")
    parser.add_argument("--verify-only", action="store_true", help="Only verify today's evidence file exists.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the evidence file if it already exists.")
    parser.add_argument(
        "--grace-days",
        type=int,
        default=0,
        help="Permit verification to succeed if an evidence file exists within the past N days (default: 0).",
    )
    args = parser.parse_args()

    try:
        if args.verify_only:
            path = verify_latest(max(args.grace_days, 0))
            print(f"[config-evidence] Found {path.relative_to(REPO_ROOT)}")
        else:
            path = generate_evidence(overwrite=args.overwrite)
            print(f"[config-evidence] Wrote {path.relative_to(REPO_ROOT)}")
    except RuntimeError as exc:
        print(f"[config-evidence] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
