"""Markdown report generator stub."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(slots=True)
class ReportGenerator:
    output_dir: Path = Path("reports/auto")

    def write_markdown(self, name: str, context: Mapping[str, object]) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{name}.md"
        lines = [f"# {name}", ""]
        for key, value in context.items():
            lines.append(f"- **{key}**: {value}")
        path.write_text("
".join(lines) + "
", encoding="utf-8")
        return path


__all__ = ["ReportGenerator"]
