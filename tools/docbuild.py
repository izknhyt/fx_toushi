"""Doc build pipeline for MkDocs output."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


class DocBuildError(Exception):
    """Base exception for doc build failures."""


class MkDocsBuildError(DocBuildError):
    """Raised when MkDocs build fails."""


@dataclass(slots=True)
class DocBuildResult:
    config_path: str
    output_dir: str
    log_path: str
    command: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "config_path": self.config_path,
            "output_dir": self.output_dir,
            "log_path": self.log_path,
            "command": list(self.command),
        }


class DocBuildPipeline:
    def __init__(
        self,
        *,
        docs_root: Path = Path("docs"),
        templates_root: Path = Path("docs/templates"),
        weekly_templates_root: Path = Path("reports/weekly/templates"),
        prompt_packages_root: Path = Path("docs/prompt_packages"),
        output_dir: Path = Path("site"),
        build_dir: Path = Path("reports/build"),
        config_path: Path = Path("mkdocs.yml"),
    ) -> None:
        self._docs_root = docs_root
        self._templates_root = templates_root
        self._weekly_templates_root = weekly_templates_root
        self._prompt_packages_root = prompt_packages_root
        self._output_dir = output_dir
        self._build_dir = build_dir
        self._config_path = config_path

    def collect_sources(self) -> list[Path]:
        sources: list[Path] = []
        for root in [
            self._docs_root,
            self._templates_root,
            self._weekly_templates_root,
            self._prompt_packages_root,
        ]:
            if root.exists():
                sources.append(root)
        return sources

    def inject_metadata(self, *, site_name: str = "FX Signal Tool Docs") -> Path:
        config_path = self._build_dir / "mkdocs.generated.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        nav = self._build_nav()
        lines = [
            f"site_name: \"{site_name}\"",
            "theme:",
            "  name: material",
            "nav:",
        ]
        for entry in nav:
            lines.append(f"  - {entry}")
        config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return config_path

    def build_site(
        self,
        *,
        clean: bool = False,
        strict: bool = False,
        run_mkdocs: bool = True,
    ) -> DocBuildResult:
        config_path = self.inject_metadata()
        command = [
            "mkdocs",
            "build",
            "--config-file",
            str(config_path),
            "--site-dir",
            str(self._output_dir),
        ]
        if clean:
            command.append("--clean")
        if strict:
            command.append("--strict")
        log_path = self._build_dir / f"docbuild_{_utcnow_stamp()}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if run_mkdocs:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
            if result.returncode != 0:
                raise MkDocsBuildError("mkdocs build failed")
        else:
            log_path.write_text(
                json.dumps({"status": "dry_run", "command": command}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return DocBuildResult(
            config_path=str(config_path),
            output_dir=str(self._output_dir),
            log_path=str(log_path),
            command=command,
        )

    def serve_site(self, *, dev_addr: str | None = None) -> DocBuildResult:
        config_path = self.inject_metadata()
        command = ["mkdocs", "serve", "--config-file", str(config_path)]
        if dev_addr:
            command.extend(["--dev-addr", dev_addr])
        log_path = self._build_dir / f"docserve_{_utcnow_stamp()}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode != 0:
            raise MkDocsBuildError("mkdocs serve failed")
        return DocBuildResult(
            config_path=str(config_path),
            output_dir=str(self._output_dir),
            log_path=str(log_path),
            command=command,
        )

    def publish_bundle(self, *, version: str | None = None) -> Path:
        version_tag = version or _utcnow_stamp()
        dist_dir = Path("dist")
        dist_dir.mkdir(parents=True, exist_ok=True)
        archive_path = dist_dir / f"docs_{version_tag}.tar.gz"
        subprocess.run(
            ["tar", "-czf", str(archive_path), "-C", str(self._output_dir), "."],
            check=True,
        )
        return archive_path

    def _build_nav(self) -> list[str]:
        entries: list[str] = []
        if self._docs_root.exists():
            entries.append("Runbooks: docs/runbooks")
            entries.append("Validation: docs/validation_playbook")
            entries.append("Templates: docs/templates")
            if (self._docs_root / "onboarding.md").exists():
                entries.append("Onboarding: docs/onboarding.md")
        return entries


def _utcnow_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _run_build(args: argparse.Namespace) -> int:
    pipeline = DocBuildPipeline()
    try:
        if args.serve:
            result = pipeline.serve_site(dev_addr=args.dev_addr)
        else:
            result = pipeline.build_site(
                clean=args.clean, strict=args.strict, run_mkdocs=not args.dry_run
            )
    except MkDocsBuildError as exc:
        print(str(exc))
        return 2
    payload = {"status": "ok", "build": result.to_dict()}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Doc build pipeline wrapper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build MkDocs site")
    build.add_argument("--clean", action="store_true", help="Clean output directory")
    build.add_argument("--strict", action="store_true", help="Fail on warnings")
    build.add_argument("--serve", action="store_true", help="Start MkDocs serve")
    build.add_argument("--dev-addr", default=None, help="MkDocs dev server address")
    build.add_argument("--dry-run", action="store_true", help="Skip mkdocs invocation")
    build.add_argument("--json", action="store_true", help="Emit JSON output")

    args = parser.parse_args()
    if args.command == "build":
        return _run_build(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["DocBuildPipeline", "DocBuildError", "MkDocsBuildError", "DocBuildResult"]
