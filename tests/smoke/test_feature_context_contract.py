"""Smoke test scaffold for validating FeatureContext/Manifest feature contracts.

This placeholder documents the expected assertions described in detailed design
§3.3.2/§3.5.5. Once FeaturePipeline and StrategyManifest loaders are
implemented, the test should:

* Instantiate a FeatureContext (or fixture) and collect ``available_keys``.
* Load ``strategy_manifest.yaml`` and gather each strategy's
  ``metadata.required_features`` set.
* Assert that every required feature is present in ``available_keys`` and
  optionally that no orphaned features exist on either side.

For the M1 scaffold this test is marked as ``smoke`` and skipped so that the CI
workflow exercises the hook without failing.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.smoke


@pytest.mark.skip(reason="Feature contract validation not implemented; scaffold only.")
def test_feature_context_available_keys_align_with_manifest() -> None:
    """Placeholder for FeatureContext vs. Manifest contract verification."""
    # The real implementation will compare FeatureContext.available_keys with
    # strategy metadata declarations from strategy_manifest.yaml.
    # See detailed_design_fx_signal_tool_v1.md §3.3.2/§3.5.5 for the contract.
    raise NotImplementedError("Contract validation will be implemented in a future packet.")
