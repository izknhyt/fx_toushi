"""Stress test engine skeleton for diagnostics CLI."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .datasets import ScenarioDataset, ScenarioDatasetRegistry


@dataclass(slots=True)
class StressTestResult:
    """Result payload exported by the engine."""

    scenario: str
    status: str
    summary: str
    artifacts: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario": self.scenario,
            "status": self.status,
            "summary": self.summary,
            "artifacts": list(self.artifacts),
        }


class StressTestEngine:
    """Minimal engine that reuses registry entries and emits summaries."""

    def __init__(self, registry: ScenarioDatasetRegistry | None = None) -> None:
        self._registry = registry or ScenarioDatasetRegistry()

    def run(self, scenario: str, *, export_dir: Path | None = None) -> StressTestResult:
        dataset = self._registry.get(scenario)
        artifacts: list[str] = []
        target_dir = export_dir or Path("reports") / "stress"
        target_dir.mkdir(parents=True, exist_ok=True)
        report_path = target_dir / f"{scenario}_report.md"
        report_content = (
            f"# Stress Test Report: {dataset.name}\n\n"
            f"- path: {dataset.path}\n"
            f"- kind: {dataset.kind}\n"
        )
        report_path.write_text(report_content, encoding="utf-8")
        artifacts.append(str(report_path))
        summary = f"Scenario '{dataset.name}' validated at {dataset.path}"
        return StressTestResult(
            scenario=dataset.name, status="ok", summary=summary, artifacts=artifacts
        )

    def list_scenarios(self) -> list[ScenarioDataset]:
        return self._registry.list()

    @classmethod
    def from_config(cls, payload: Iterable[Mapping[str, object]]) -> StressTestEngine:
        registry = ScenarioDatasetRegistry.from_mapping(payload)
        return cls(registry=registry)
