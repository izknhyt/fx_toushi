from __future__ import annotations

from pathlib import Path

from tools.scripts.run_v2_completion_check_daily import PROJECT_ROOT


def test_run_v2_completion_check_daily_project_root_points_repo() -> None:
    assert (PROJECT_ROOT / "tools" / "scripts" / "run_v2_completion_check_daily.py").exists()
    assert (PROJECT_ROOT / "config" / "ops" / "v2_completion_check_daily.cron").exists()
