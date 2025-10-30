"""Placeholder smoke test for config schema validation."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.config_schema_smoke


@pytest.mark.xfail(reason="Config schema smoke harness not implemented", raises=NotImplementedError, strict=True)
def test_config_schema_smoke_placeholder() -> None:
    """Track missing implementation for config schema smoke test."""

    raise NotImplementedError("Implement config schema smoke validation per PKG-CONFIG-SCHEMA-01")
