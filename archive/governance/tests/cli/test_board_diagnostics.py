from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli import create_cli_app
from typer.testing import CliRunner


def _write_events(path: Path, events: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(evt, ensure_ascii=False) for evt in events) + "\n",
        encoding="utf-8",
    )


def test_board_diagnostics_detects_diff(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    log_path = tmp_path / "registry.log"
    _write_events(
        log_path,
        [
            {"event": "strategy.determinism", "strategy_id": "s1", "determinism_hash": "h1"},
            {"event": "strategy.determinism", "strategy_id": "s1", "determinism_hash": "h2"},
        ],
    )
    result = runner.invoke(
        app, ["diagnostics", "board", "--log", str(log_path), "--json"]
    )
    assert result.exit_code == 76
    payload = json.loads(result.stdout)
    assert payload["status"] == "diff"
    assert payload["diff_strategies"]["s1"] == ["h1", "h2"]


def test_board_diagnostics_ok_when_consistent(tmp_path: Path) -> None:
    app = create_cli_app()
    runner = CliRunner()
    log_path = tmp_path / "registry.log"
    _write_events(
        log_path,
        [
            {"event": "strategy.determinism", "strategy_id": "s1", "determinism_hash": "h1"},
            {"event": "strategy.determinism", "strategy_id": "s1", "determinism_hash": "h1"},
        ],
    )
    result = runner.invoke(
        app, ["diagnostics", "board", "--log", str(log_path), "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["summary"]["diff_count"] == 0
