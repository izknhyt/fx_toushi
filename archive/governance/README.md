# archive/governance/

Governance, ceremony, and v2 completion-check material retired for personal use per [docs/architecture.md](../../docs/architecture.md) §5.

## Contents

- `src/portfolio/` — v2 multi-pair expansion ceremony (`multi_pair_cycle_completion`, `multi_pair_next_expansion*`, `multi_pair_next_review_bridge`, `multi_pair_post_qualification`, `multi_pair_steady_state`, `v2_completion_evidence`, `shadow_feedback_*`, etc.). The clean admission layer will be rebuilt under `src/admission/`.
- `src/ops/` — OpsAgendaService scaffolding and drill orchestration.
- `src/interfaces/gui/` — v2 completion-check GUI surfaces and shadow-daily-ops summaries.
- `tools/scripts/run_v2_completion_check*`, `tools/render_v2_completion_evidence.py`, `tools/gui_ops_loop.py` — supporting scripts.
- `config/ops/launchd/`, `config/ops/v2_completion_check_daily.cron` — scheduled v2 check apparatus.
- `docs/trader_signoff/`, `docs/change_requests/`, `docs/risk_review/`, `docs/legal/`, `docs/backoffice/`, `docs/rebalance/`, `docs/governance/`, `docs/release_checklist.md`, `docs/onboarding.md` — multi-role approval docs.
- `docs/development_plan.md` — the update-log ceremony that was driving the "touch every change with doc edits" overhead.
- `docs/fx_portfolio_completion_blueprint.md`, `docs/fx_portfolio_development_team.md`, `docs/fx_portfolio_tool_v2_*` — v2 planning artifacts.
- `operational_logs/` — `audit.jsonl`, `audit_pack/`, `ops_worklog.jsonl`, `automation_effect.jsonl`, `ignored.jsonl`.

## Rule

**Do not re-wire any of this into the live codebase.** If a workflow here turns out to be genuinely useful, extract the minimum viable piece and place it under `src/` with a justification against [CLAUDE.md](../../CLAUDE.md).
