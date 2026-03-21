from __future__ import annotations

import json
from pathlib import Path

from tools.run_shadow_multi_pair_preparation import run_multi_pair_preparation


def test_run_multi_pair_preparation_renders_packet_without_running(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    data_dir = tmp_path / "curated"
    for symbol in ("usdjpy", "eurusd"):
        symbol_dir = data_dir / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        (symbol_dir / f"{symbol}_m5_20240101_20240102_merged.parquet").write_text(
            "stub",
            encoding="utf-8",
        )
    manifest_path = tmp_path / "strategy_manifest.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "strategies:",
                "  - id: alpha",
                "    enabled: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    data_manifest = tmp_path / "data_manifest.json"
    data_manifest.write_text(
        "{\"strategies\": {\"alpha\": {\"dataset_path\": \""
        + str(tmp_path / "alpha.parquet")
        + "\"}}}",
        encoding="utf-8",
    )

    payload = run_multi_pair_preparation(
        manifest_path=manifest_path,
        allocation_config_path=tmp_path / "strategy_allocation.yaml",
        allocation_profile="portfolio_admission_v2",
        data_path=tmp_path / "alpha.parquet",
        next_symbol="eurusd",
        profile_path=tmp_path / "paper.yaml",
        data_dir=data_dir,
        feature_config=tmp_path / "feature_pipeline.yaml",
        data_manifest=data_manifest,
        windows=("2016_2025", "2022_2025"),
        output_dir=output_dir,
        output_prefix="shadow_multi_pair_preparation",
        run=False,
    )

    packet = payload["packet"]
    assert payload["status"] == "ok"
    assert packet["status"] == "ready"
    assert packet["next_symbol"] == "EURUSD"
    assert packet["required_inputs"] == []
    assert packet["commands"][0]["step"] == "baseline_kernel_validation"
    assert packet["commands"][1]["step"] == "kernel_validation"
    assert packet["commands"][2]["step"] == "candidate_snapshot"
    assert packet["commands"][3]["step"] == "admission_snapshot"
    assert packet["baseline_symbols"] == ["USDJPY"]
    assert packet["symbol_scope"] == ["USDJPY", "EURUSD"]
    assert packet["effective_data_manifest"].endswith("shadow_multi_pair_eurusd_data_manifest.json")
    assert json.loads(Path(payload["json_path"]).read_text(encoding="utf-8"))["next_symbol"] == "EURUSD"
    assert Path(payload["json_path"]).exists()
    assert Path(payload["markdown_path"]).exists()
    assert payload["json_path"].endswith(".json")
    assert payload["markdown_path"].endswith(".md")
    assert "shadow_multi_pair_preparation" in payload["json_path"]
    assert "shadow_multi_pair_eurusd_validation.json" in packet["artifacts"]["validation_summary_json"]
