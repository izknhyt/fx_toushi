from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.interfaces.cli.board import board


SNAPSHOT_DIR = Path(__file__).parent / "board"


@pytest.mark.parametrize(
    "name",
    [
        "normal_signed",
        "guarded_pending",
        "spread_block",
        "kill_switch_hard",
        "reduce_only_warning",
        "cooldown_normal",
        "expired_guarded",
        "watch_warning",
        "watch_reduce_only",
        "watch_soft_warning",
        "watch_expired",
        "spread_block_soft_warning",
        "normal_double_entry_pending",
        "latency_reduce_only",
    ],
)
def test_board_render_matches_snapshots(name: str, tmp_path: Path) -> None:
    snapshot_path = SNAPSHOT_DIR / f"{name}.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    guardrails = snapshot["guardrails"]

    manifest = tmp_path / "reports/data_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "strategies": {
                    "m1_baseline_ma_rsi": {
                        "dataset_path": "data/mock.parquet",
                        "dataset_sha256": "sha256:fixture",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    payload = board(
        view="tickets",
        guarded=snapshot.get("board_mode") == "guarded",
        normal=snapshot.get("board_mode") == "normal",
        kill_switch_state=guardrails.get("kill_switch_state"),
        spread_status=guardrails.get("spread_status"),
        reduce_only=guardrails.get("reduce_only", False),
        risk_disclosure_status=guardrails.get("risk_disclosure"),
        tickets=snapshot.get("tickets", []),
        manifest_path=manifest,
        rich_table=True,
    )

    assert payload["guardrails"]["kill_switch_state"] == guardrails["kill_switch_state"]
    assert payload["guardrails"]["spread_status"] == guardrails["spread_status"]
    assert payload["guardrails"]["reduce_only"] == guardrails["reduce_only"]
    assert payload["guardrails"]["risk_disclosure"] == guardrails["risk_disclosure"]
    assert payload["render_summary"] == snapshot["render_summary"]
    assert payload["rendered_table"].strip() == str(snapshot["rendered_table"]).strip()
