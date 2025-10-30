"""Placeholder for `tradectl data status` stage evaluation flow."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.data_status_cli


@pytest.mark.xfail(reason="Data status CLI automation not implemented", raises=NotImplementedError, strict=True)
def test_data_status_cli_stage_eval_placeholder() -> None:
    """Ensure CLI stage evaluation logging is covered once implementation lands."""

    raise NotImplementedError("Implement stage_eval assertions per PKG-DATA-STATUS-01")
