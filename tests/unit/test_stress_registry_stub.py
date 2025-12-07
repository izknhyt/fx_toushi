from __future__ import annotations

from pathlib import Path

from src.stress import ScenarioDataset, ScenarioDatasetRegistry, StressTestEngine


def test_scenario_registry_registers_and_validates(tmp_path: Path) -> None:
    registry = ScenarioDatasetRegistry()
    dataset_path = tmp_path / "shock.csv"
    dataset_path.write_text("ts,shock\n2025-01-01,0.1\n", encoding="utf-8")
    registry.register(ScenarioDataset(name="brexit", path=dataset_path, description="Brexit shock"))

    summaries = registry.validate()
    assert summaries[0]["name"] == "brexit"
    assert summaries[0]["exists"] is True


def test_stress_engine_runs_registered_scenario(tmp_path: Path) -> None:
    registry = ScenarioDatasetRegistry()
    registry.register(ScenarioDataset(name="flash_crash", path=tmp_path / "flash.csv"))
    engine = StressTestEngine(registry=registry)

    result = engine.run("flash_crash", export_dir=tmp_path / "reports")
    assert result.status == "ok"
    assert "flash_crash" in result.summary
