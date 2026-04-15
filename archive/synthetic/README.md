# archive/synthetic/

Reports and metrics that looked like evidence but were **stubs, templates, or synthetic-dataset output**. Retired here so they stop misleading decisions.

## Why this directory exists

In the prior layout, `reports/backtest/m1_baseline/wf/20251111/walk_forward_segments.json` contained all 48 walk-forward segments cycling through the same three PF / Sharpe values (`1.20 / 0.93`, `1.22 / 0.96`, `1.18 / 0.90`). This is mathematically impossible on real price data. Similar templated patterns appeared in the IS summary and validation notes.

This material predated the evidence discipline in [CLAUDE.md](../../CLAUDE.md). It is preserved here only so we remember what a stub looks like.

## Contents

- `reports/backtest/m1_baseline/` — scaffolding backtest of the retired `ma_rsi` strategy against a synthetic dataset.
- `reports/research/m1_baseline/` — validation summary with hardcoded round numbers.
- Any future stub caught by the `evidence-auditor` subagent lands here with a note.

## Rule

**Never copy a number out of `archive/synthetic/` into a live report, slide, or README.** If you are tempted to, the charter discipline has failed and the fix is to regenerate from real pipeline output — not to re-use the stub.
