"""Strategy manifest governance tests (PKG-STRAT-MANIFEST-01)."""

from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy

import pytest

from src.strategies.registry import ManifestValidationError, StrategyManifest

pytestmark = pytest.mark.strategy_manifest


def _manifest_payload(project_root):
    manifest_path = project_root / "config" / "strategy_manifest.yaml"
    manifest = StrategyManifest.load(manifest_path)
    return manifest.model_dump(mode="json")


def test_watchlist_symbols_must_exist_in_feature_context(project_root) -> None:
    """Watchlists referencing unavailable symbols should raise ManifestValidationError."""

    payload = _manifest_payload(project_root)
    payload["strategies"]["m1_baseline_ma_rsi"]["watchlist"] = ["USDJPY", "BTCUSD"]
    manifest = StrategyManifest.from_dict(payload)

    with pytest.raises(ManifestValidationError, match="watchlist"):
        manifest.validate_watchlists({"USDJPY", "EURUSD"})


def test_lifecycle_auto_deprecates_after_validation_window(project_root) -> None:
    """Enabled strategies become invalid when validation is stale (> deprecated_after_days)."""

    payload = _manifest_payload(project_root)
    lifecycle = payload["strategies"]["m1_baseline_ma_rsi"]["lifecycle"]
    lifecycle["last_validated_at"] = "2024-01-01T00:00:00Z"
    lifecycle["deprecated_after_days"] = 30

    manifest = StrategyManifest.from_dict(payload)
    stale_reference = datetime(2024, 2, 15, tzinfo=timezone.utc)

    with pytest.raises(ManifestValidationError, match="lifecycle"):
        manifest.validate_lifecycle(now=stale_reference)


def test_resolve_watchlist_ignores_deprecated_entries(project_root) -> None:
    """Deprecated lifecycle entries must not contribute to the effective watchlist."""

    payload = _manifest_payload(project_root)
    manifest = StrategyManifest.from_dict(deepcopy(payload))
    manifest.validate_lifecycle()  # ensure baseline passes

    resolved = manifest.resolve_watchlist({"USDJPY", "EURUSD"})
    assert resolved == frozenset({"USDJPY", "EURUSD"})

    payload["strategies"]["m1_baseline_ma_rsi"]["lifecycle"]["status"] = "deprecated"
    stale_manifest = StrategyManifest.from_dict(payload)

    with pytest.raises(ManifestValidationError, match="deprecated"):
        stale_manifest.validate_lifecycle()
