from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from src.interfaces.cli import create_cli_app


def _hash_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_research_experiment_flow(tmp_path: Path, monkeypatch) -> None:
    app = create_cli_app()
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    data_manifest = tmp_path / "reports" / "data_manifest.json"
    data_manifest.parent.mkdir(parents=True, exist_ok=True)
    data_manifest.write_text(json.dumps({"status": "baseline"}), encoding="utf-8")
    dataset_hash = _hash_path(data_manifest)

    init_result = runner.invoke(
        app,
        [
            "research",
            "experiment",
            "init",
            "--manifest",
            "exp-1",
            "--strategy",
            "strat-a",
            "--owner",
            "user:alice",
            "--objective",
            "baseline test",
            "--json",
        ],
    )
    assert init_result.exit_code == 0, init_result.stdout

    run_result = runner.invoke(
        app,
        [
            "research",
            "experiment",
            "run",
            "--manifest",
            "exp-1",
            "--mode",
            "backtest",
            "--metric",
            "pf=1.2",
            "--metric",
            "sharpe=0.9",
            "--metric",
            "max_dd=0.1",
            "--metric",
            "trades=40",
            "--dataset-hash",
            dataset_hash,
            "--complete",
            "--json",
        ],
    )
    assert run_result.exit_code == 0, run_result.stdout
    run_payload = json.loads(run_result.stdout)
    run_id = run_payload["run"]["run_id"]

    list_result = runner.invoke(app, ["research", "experiment", "list", "--json"])
    assert list_result.exit_code == 0, list_result.stdout
    list_payload = json.loads(list_result.stdout)
    assert list_payload["count"] == 1

    promote_result = runner.invoke(
        app,
        [
            "research",
            "experiment",
            "promote",
            "--run",
            run_id,
            "--target",
            "paper_candidate",
            "--json",
        ],
    )
    assert promote_result.exit_code == 0, promote_result.stdout
    promote_payload = json.loads(promote_result.stdout)
    assert promote_payload["status"] == "ok"
