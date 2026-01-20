#!/usr/bin/env python3
"""Notebook runner for research workflows."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class NotebookRunResult:
    status: str
    notebook_path: str
    output_path: str | None
    report_path: str
    executed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "notebook_path": self.notebook_path,
            "output_path": self.output_path,
            "report_path": self.report_path,
            "executed": self.executed,
        }


class NotebookRunner:
    def __init__(self, *, report_dir: Path = Path("reports") / "research" / "notebooks") -> None:
        self._report_dir = report_dir

    def run(
        self,
        *,
        notebook_path: Path,
        output_dir: Path | None = None,
        execute: bool = False,
    ) -> NotebookRunResult:
        if not notebook_path.exists():
            raise FileNotFoundError(str(notebook_path))
        output_dir = output_dir or (Path("reports") / "research" / "notebooks")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path: Path | None = None
        executed = False
        status = "skipped"
        if execute and shutil.which("jupyter"):
            output_path = output_dir / f"{notebook_path.stem}_executed.ipynb"
            command = [
                "jupyter",
                "nbconvert",
                "--execute",
                "--to",
                "notebook",
                "--output",
                str(output_path),
                str(notebook_path),
            ]
            result = subprocess.run(command, check=False)
            executed = result.returncode == 0 and output_path.exists()
            status = "ok" if executed else "error"
        elif execute:
            status = "error"
        report_path = self._write_report(
            notebook_path=notebook_path,
            output_path=output_path,
            status=status,
            executed=executed,
        )
        return NotebookRunResult(
            status=status,
            notebook_path=str(notebook_path),
            output_path=str(output_path) if output_path else None,
            report_path=str(report_path),
            executed=executed,
        )

    def _write_report(
        self,
        *,
        notebook_path: Path,
        output_path: Path | None,
        status: str,
        executed: bool,
    ) -> Path:
        self._report_dir.mkdir(parents=True, exist_ok=True)
        report_path = self._report_dir / f"notebook_run_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.md"
        lines = [
            "# Research Notebook Run",
            "",
            f"- Notebook: {notebook_path}",
            f"- Status: {status}",
            f"- Executed: {executed}",
            f"- Output: {output_path}" if output_path else "- Output: (none)",
            f"- Generated at: {_utcnow_iso()}",
        ]
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return report_path


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run research notebooks.")
    parser.add_argument("--path", required=True, help="Notebook path")
    parser.add_argument("--execute", action="store_true", help="Execute notebook")
    parser.add_argument("--out", default=None, help="Output directory")
    args = parser.parse_args()

    runner = NotebookRunner()
    result = runner.run(
        notebook_path=Path(args.path),
        output_dir=Path(args.out) if args.out else None,
        execute=args.execute,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.status in {"ok", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
