# archive/

Retired code, docs, and evidence. **Read-only.** Do not import from here. Do not reference these files from anything under `src/`, `config/`, `docs/`, or `tests/`.

Material lives here so that:

- Git history is preserved without polluting active paths.
- We can recover context if a decision turns out to depend on something retired.
- The live codebase stays aimed at the single goal: **trading USDJPY profitably** (see [../CLAUDE.md](../CLAUDE.md)).

## Subtrees

- [`enterprise/`](enterprise/) — multi-role governance modules dropped for personal use (compliance, backoffice, trader sign-off, audit, release gating, etc.). Listed in arch §8.2 "what we drop".
- [`synthetic/`](synthetic/) — stub or templated evidence that was masquerading as real backtest output. Kept for forensic reference, never treat as evidence.
- [`legacy/`](legacy/) — superseded design documents (legacy detailed design, original requirements templates).
- [`governance/`](governance/) — v2 completion-check loops, multi-pair expansion ceremonies, development plan & update log apparatus.

## Retention

If a subtree sees no access for two months, it is a candidate for deletion. Do not delete without confirming the material is not referenced anywhere that still matters.
