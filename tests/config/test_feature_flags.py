from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.mark.feature_flags
def test_defaults_cover_all_defined_flags(
    load_config: Callable[[str | Path], object],
) -> None:
    config = load_config("config/feature_flags.yaml")

    definitions = config["definitions"]
    defaults = config["defaults"]

    for env_name, env_flags in defaults.items():
        missing = set(definitions.keys()) - set(env_flags.keys())
        assert not missing, f"{env_name} is missing defaults for: {sorted(missing)}"

        unexpected = set(env_flags.keys()) - set(definitions.keys())
        assert not unexpected, f"{env_name} defines unknown flags: {sorted(unexpected)}"


@pytest.mark.feature_flags
def test_dangerous_flags_have_strict_governance(
    load_config: Callable[[str | Path], object],
) -> None:
    config = load_config("config/feature_flags.yaml")

    dangerous = {
        name: definition
        for name, definition in config["definitions"].items()
        if definition["category"] == "dangerous"
    }

    assert dangerous, "Expected at least one dangerous feature flag definition."

    for name, definition in dangerous.items():
        conditions = definition["enable_conditions"]
        rollback = definition["rollback"]
        assert len(conditions) >= 2, f"{name} should list at least two enable conditions."
        assert len(rollback) >= 2, f"{name} should list at least two rollback steps."


@pytest.mark.feature_flags
def test_runbook_refs_point_to_feature_flag_runbook(
    load_config: Callable[[str | Path], object],
) -> None:
    config = load_config("config/feature_flags.yaml")

    for name, definition in config["definitions"].items():
        runbook_ref = definition["runbook_ref"]
        assert runbook_ref.startswith("RUN-FEATURE-FLAG-01"), (
            f"{name} should reference RUN-FEATURE-FLAG-01, got {runbook_ref!r}"
        )
