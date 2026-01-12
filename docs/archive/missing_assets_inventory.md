# Missing Asset Inventory (from detailed_design_fx_signal_tool_v1.md)

This inventory focuses on M1-core references that are missing in the repo.
Templates and schemas were added to unblock implementation work.

## Created (M1+ scaffolds added in follow-up)
- config/brokers/README.md
- config/brokers/sandbox.yaml
- config/brokers/error_map.yaml
- config/brokers/slo.yaml
- config/broker/README.md
- config/calendar/business_days.yaml
- config/compliance/pretrade_rules_TEMPLATE.yaml
- config/compliance/risk_disclosure_TEMPLATE.yaml
- config/concurrency_profiles.yaml
- config/drift_monitor.yaml
- config/emergency.yaml
- config/gates.spread_max_pips
- config/hedge_routes.yaml
- config/idea_pipeline.yaml
- config/ideas.yaml
- config/model_risk.yaml
- config/ops/workload_defaults.yaml
- config/providers/real_time_candidates.yaml
- config/reconciliation.yaml
- config/regression.yaml
- config/reports/kpi.yaml
- config/resource_budget.yaml
- config/risk/margin_stress_presets.yaml
- config/secret/README.md
- config/secret/metadata.json
- config/shadow/channels.yaml
- config/shadow/tokens.yaml
- config/share_profiles/README.md
- config/share_profiles/TEMPLATE.yaml
- config/signatures/README.md
- config/signatures/index.json
- config/sla_thresholds/candidate_template.yaml
- schema/broker_sandbox.schema.json
- schema/broker_error_map.schema.json
- schema/broker_slo.schema.json
- schema/business_days.schema.json
- schema/compliance_pretrade_rules.schema.json
- schema/compliance_risk_disclosure.schema.json
- schema/concurrency_profiles.schema.json
- schema/drift_monitor.schema.json
- schema/emergency.schema.json
- schema/spread_max_pips.schema.json
- schema/hedge_routes.schema.json
- schema/idea_pipeline.schema.json
- schema/ideas.schema.json
- schema/model_risk.schema.json
- schema/ops_workload_defaults.schema.json
- schema/real_time_candidates.schema.json
- schema/reconciliation.schema.json
- schema/regression.schema.json
- schema/reports_kpi.schema.json
- schema/resource_budget.schema.json
- schema/margin_stress_presets.schema.json
- schema/shadow_channels.schema.json
- schema/shadow_tokens.schema.json
- schema/share_profiles.schema.json
- schema/signatures_index.schema.json
- schema/sla_threshold_candidate.schema.json

## Remaining (intentionally deferred or placeholder patterns)
- docs/change_requests/* placeholders (CR-*, ALPHA-*, etc.)
- reports/* placeholders with date suffixes (YYYYMMDD, templates, etc.)
- logs/* sample paths with date suffixes (YYYYMMDD, *.zst, etc.)
- data/* sample datasets listed as examples in design

