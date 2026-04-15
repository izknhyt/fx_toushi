# Project charter for Claude Code

**Purpose: build a USDJPY-first FX portfolio operating system that trades profitably over time.**

Everything in this repo serves one question: *does this change make us more likely to win money?* If the answer is no, cut it.

This is personal-use. Not an enterprise trading platform. Not a strategy zoo. Not a governance tool.

Read [docs/architecture.md](docs/architecture.md) before any non-trivial change. When architecture and code disagree, architecture wins.

## The 10 invariants

1. `Candidate` contract: strategies emit `Candidate`, nothing else. 13 fields required (see `src/contract.py`).
2. `portfolio_utility = expected_return - drawdown_penalty - trading_cost - slot_time_penalty - correlation_penalty` is the optimization target.
3. Admission layer is the core decision point (`accept` / `reject` / `defer` / `resize` / `replace`).
4. `admission_score = expected_edge - estimated_cost - holding_penalty - correlation_penalty - conflict_penalty`.
5. One decision path: backtest / shadow / live share `src/decision_path.py`.
6. No-trade is a valid decision. Ambiguous cases default to reject.
7. 3 gates to adopt a strategy: standalone → marginal contribution → shadow.
8. Portfolio metadata required on every candidate (`portfolio_group`, `role_priority`, `expected_holding_minutes`, `slot_cost`, `exposure_bucket`, `max_active_per_group`, `replacement_policy`).
9. Feedback layer outputs `penalty` / `override` / `block` — not dashboards.
10. Structural pair neutrality: USDJPY-first, but no USDJPY-only hardcoding.

## Directory contract (target state)

The new minimal skeleton is:

- `src/` has exactly: `data/`, `regime/`, `strategies/`, `admission/`, `execution/`, `risk/`, `feedback/`, `decision_path.py`, `contract.py`. Adding a new top-level subdir requires updating this charter first.
- `config/` has exactly 3 files: `execution.yaml`, `portfolio.yaml`, `strategy.yaml`.
- `reports/` = real outputs only. Stubs go to `archive/synthetic/`.
- `archive/` = retired code / docs. Read-only. Never import from it.

The current repo is transitioning toward this shape. Existing extra dirs are being moved to `archive/` in phases; do not add new ones.

## What does NOT belong here

Dropped as over-engineering for personal use (arch §8.2). If a task seems to require any of these, stop and ask whether scope really grew, or whether a lighter mechanism works.

- Trader sign-off, multi-role approval, audit bundle generation
- Compliance / backoffice / governance / release / reconciliation modules
- Change-request templates, promotion paperwork
- Heavy runbooks unrelated to personal kill-switch operation
- Multi-pair expansion ceremony (`*_cycle_completion`, `*_post_qualification`, `*_steady_state`, `*_next_expansion_rollout`, `*_next_review_bridge`, `*_completion_evidence`)
- Development plan / update-log ceremonies

## Evidence discipline

- A file under `reports/` is evidence **only if** generated from real pipeline execution in this repo.
- Hardcoded, templated, or repeating numeric patterns = stub, not evidence.
- Every report must carry its generating command + commit hash (inline or sidecar).
- Spot a stub? Move it to `archive/synthetic/` and note why.

## CI gates (must pass to merge)

- `test_contract`  — all strategies emit valid `Candidate` objects.
- `test_parity`    — backtest / shadow / live decisions match for fixed seed.
- `test_cost`      — cost > 0 under every non-zero config.

These gates are the skeleton of trust. Failing them does not mean "write a workaround"; it means "the change is wrong, or the charter is wrong — pick one and fix it."

## Before you write code

- Ask: does this move us closer to making money? If not, stop.
- Prefer editing over adding. The codebase should shrink this quarter.
- If you are about to add a new subdir / config file / dependency / ceremony file, stop and justify against the 10 invariants.
- If you discover dead or ceremonial code while working, archive it in the same PR.

## Subagents and skills

- `charter-guard` — reviews proposed changes against this charter before commit.
- `alpha-critic` — challenges a proposed alpha hypothesis before it becomes code.
- `evidence-auditor` — detects stub / synthetic reports.
- `/new-strategy` — scaffolds a strategy with the `Candidate` contract pre-wired.

See [.claude/agents/](.claude/agents/) and [.claude/skills/](.claude/skills/).

Last updated: 2026-04-15
