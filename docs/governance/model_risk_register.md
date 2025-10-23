---
register_version: 1
schema_version: model_risk_register_v1
updated_at: 2025-02-25
review_cycle_days: 90
validation_playbook_id: AC-52_model_risk
---

# Model Risk Register (Template)

Model Risk Register entries are managed in Markdown. Each strategy is documented as a section under `## Strategy <id>` with a
standardised table describing risk posture, required evidence, mitigation tasks, and the most recent review artefacts. Reviewers
update this file directly through Pull Requests so that Git history provides the authoritative change log.

> **Note**
> When automation pipelines require machine-readable metadata, generate `docs/governance/model_risk_register.meta.yaml` from this
> Markdown source. The YAML file is supplementary only; `model_risk_register.md` remains the source of truth. Generation scripts
> MUST append an event to `logs/audit/model_risk_register_<YYYYMMDD>.jsonl` describing the export command, git revision, and checksum
> of both files.

## How to Update

1. Open a Pull Request modifying the relevant strategy section in this Markdown file.
2. Run `tradectl model-risk render-meta --source docs/governance/model_risk_register.md` to refresh the optional YAML metadata when
   downstream services still depend on it.
3. Attach evidence artefacts under `reports/model_risk/<strategy_id>/<YYYYMMDD>/` and list their relative paths in the table.
4. Record the update in the Validation Data Playbook entry `reports/validation_log/AC-52_model_risk.md`, including reviewer
   signatures and hashes of uploaded artefacts.

## Strategy Entry Template

### Strategy `<strategy_id>`

| Field | Description | Example |
| --- | --- | --- |
| `version` | Register entry revision or trading model version. | `2025.02-r1` |
| `risk_level` | One of `low`, `medium`, or `high`. | `medium` |
| `last_reviewed_at` | Date of the most recent approval. | `2025-02-24` |
| `next_review_due` | ISO date for the next mandatory review. | `2025-05-25` |
| `reviewers` | Approver names and roles. | `Jane Quant (Quant Lead); Alex Ops (Ops Manager)` |
| `status` | `pending`, `approved`, `expired`, or `blocked`. | `approved` |
| `watchlist` | `true` if the strategy is under heightened monitoring. | `false` |
| `issues` | Reference to open `RiskIssue` identifiers documented below. | `MR-2025-014` |
| `mitigations` | Summary of mitigation steps and owners. | `Retrain with February dataset by 2025-03-15 (Data Ops)` |
| `evidence_refs` | Relative paths to Explainability artefacts or tickets. | `reports/model_risk/alpha_usd/20250224/shap_summary.png` |
| `residual_risk` | Narrative of remaining risk accepted by governance. | `Explainability delta accepted for pilot exposure.` |

Below each strategy table, enumerate `RiskIssue` entries using bullet lists:

```
- MR-2025-014 (`category=explainability`, `severity=high`)
  - Description: SHAP residual drift observed for USDJPY.
  - Mitigation: Retrain using January + February fills, rerun ICE plots.
  - Evidence: tickets/model_revalidate/MR-2025-014.md
  - Status: `open`
```

## Register Metadata

- **Source of truth**: `docs/governance/model_risk_register.md` (this file).
- **Supplementary export**: `docs/governance/model_risk_register.meta.yaml` (generated).
- **Audit trail**: `logs/audit/model_risk_register_<YYYYMMDD>.jsonl` appended by automation.
- **Runbook linkage**: Follow `docs/runbooks/GOV-STRAT-01.md` for Explainability production and review.
- **Validation Data Playbook**: Update `reports/validation_log/AC-52_model_risk.md` after every review cycle.
