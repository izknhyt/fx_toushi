# archive/enterprise/

Modules that served an enterprise / multi-user operating model. Retired for personal use per [docs/architecture.md](../../docs/architecture.md) §5.

Retired subtrees include:

- `src/compliance/` — regulatory compliance
- `src/backoffice/` — back-office workflows
- `src/governance/` — governance orchestration
- `src/trader/` — trader-facing controls and sign-off
- `src/audit/` — audit bundle generation
- `src/release/` — release gating
- `src/reconciliation/` — post-trade reconciliation
- `src/security/` — access control scaffolding
- `src/ops_readiness/` — readiness ceremonies
- `src/account/`, `src/accounts/` — multi-account management
- `src/journal/` — trading journal ceremony
- `src/ticket/` — ticket workflow
- `src/docops/` — docs ceremony
- `src/scoreboard/` — scoring ceremony
- `src/strategies/ma_rsi.py` — explicit "scaffolding tests" strategy

Rule: **never import from this subtree.** If something here turns out to be essential, rewrite a minimal version under `src/` rather than re-enabling the full module.
