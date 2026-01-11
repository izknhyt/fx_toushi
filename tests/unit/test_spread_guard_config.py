from __future__ import annotations

from pathlib import Path

from src.core.spread_guard import resolve_news_block_window, resolve_spread_guard_multiplier


def test_spread_guard_manifest_window_and_multiplier(tmp_path: Path) -> None:
    manifest = tmp_path / "strategy_manifest.yaml"
    manifest.write_text(
        "\n".join(
            [
                "strategies:",
                "  strat_a:",
                "    parameters:",
                "      filters:",
                "        news_block_minutes: [-10, 20]",
                "        spread_guard_multiplier: 1.8",
                "  strat_b:",
                "    filters:",
                "      news_block_minutes: [-15, 30]",
                "      spread_guard_multiplier: 2.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert resolve_news_block_window(manifest) == (-15, 30)
    assert resolve_spread_guard_multiplier(manifest) == 2.0
