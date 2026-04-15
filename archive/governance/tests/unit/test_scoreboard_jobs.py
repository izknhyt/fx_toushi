from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.scoreboard.jobs_stub import run_weekly_job


@dataclass
class DummySnapshot:
    week: str
    mode: str
    strategies: list[str]


class DummyService:
    def generate_weekly_snapshot(self, *, week: str | None = None, mode: str = "live", **_: object) -> DummySnapshot:
        return DummySnapshot(week=week or "2024-W01", mode=mode, strategies=["s1", "s2"])


def test_run_weekly_job_writes_metrics(tmp_path: Path) -> None:
    metrics_path = tmp_path / "scoreboard_jobs.jsonl"

    job_id = run_weekly_job(
        week="2024-W02",
        mode="paper",
        metrics_path=metrics_path,
        service=DummyService(),
    )

    assert job_id.startswith("scoreboard-weekly-")
    lines = metrics_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert "2024-W02" in lines[0]
