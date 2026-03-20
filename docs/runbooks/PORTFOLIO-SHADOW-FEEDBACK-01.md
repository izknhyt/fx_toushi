# PORTFOLIO-SHADOW-FEEDBACK-01

- Version: `0.1`
- Last Updated: `2026-03-20`
- Owner: `Codex / Portfolio OS`

## Purpose
Run focused validation for a materialized `shadow_feedback_override_packet` before promoting any allocator override into runtime guardrails.

## Preconditions
- A daily shadow review or ops summary exists and includes `shadow_feedback_override_packet`.
- A merged validation dataset is available.
- The active allocation profile is `portfolio_admission_v2` unless explicitly overridden.

## Command
```bash
tradectl portfolio shadow-feedback-validate \
  --override-packet-json <shadow_feedback_override_packet_json> \
  --data-path <merged_data_path> \
  --windows 2016_2021,2016_2025 \
  --run
```

## Expected Outputs
- JSON summary under `reports/analysis/shadow/feedback_validation/` or the provided `--output-dir`
- Markdown summary under the same directory
- Optional runtime guardrail JSON when `--runtime-guardrail-path` is provided and the decision is `adopt`

## Decision Rules
- `adopt`
  Apply runtime guardrail only after reviewing the validation artifact.
- `hold`
  Keep the current allocation profile and continue shadow monitoring.
- `reject`
  Do not activate runtime guardrail overrides; review discrepancy causes first.

## Follow-up
- Record the artifact path in [docs/development_plan.md](/Users/izumimotohayato/development/codex_invest/docs/development_plan.md) when used for a development task.
- If the result is `adopt`, pass the generated runtime guardrail JSON to the runtime path or `TRADECTL_RUNTIME_GUARDRAIL_PATH`.
