# Architecture — slim charter entry point

Status: active reference.
Goal: build a USDJPY-first FX portfolio operating system that **trades profitably over time**. Nothing in this file exists for any reason other than to make winning more likely.

For deeper background on each principle, see [docs/architecture/fx_portfolio_operating_system.md](architecture/fx_portfolio_operating_system.md). When that document and this one conflict, **this one wins** — it is the current source of truth.

## 1. The single purpose

Trade USDJPY (and eventually multi-pair) in a way that grows capital while keeping drawdown bounded. We optimize:

```
portfolio_utility = expected_return - drawdown_penalty - trading_cost - slot_time_penalty - correlation_penalty
```

Individual strategy PF is **not** the optimization target. Marginal contribution to `portfolio_utility` is.

## 2. The 10 invariants

1. **Candidate contract.** Strategies emit `Candidate` (13 fields, see `src/contract.py`). Nothing else.
2. **Utility target.** `portfolio_utility` above is what we maximize.
3. **Admission is the core.** A central admission layer decides `accept / reject / defer / resize / replace`. Strategies do not place orders.
4. **Admission score.** `admission_score = expected_edge - estimated_cost - holding_penalty - correlation_penalty - conflict_penalty`.
5. **One decision path.** `src/decision_path.py` is shared by backtest / shadow / live. No mode-specific shortcuts.
6. **No-trade is valid.** Ambiguity defaults to `reject`, not `accept`.
7. **3 gates to adopt a strategy.** Standalone → marginal contribution → shadow. A strategy strong only on the first two is not enough.
8. **Portfolio metadata on every candidate.** `portfolio_group`, `role_priority`, `expected_holding_minutes`, `slot_cost`, `exposure_bucket`, `max_active_per_group`, `replacement_policy`.
9. **Feedback is a control loop.** Feedback layer produces `penalty` / `override` / `block` — not dashboards. Three-stage intervention: penalty → group/session block → demote/replace.
10. **Pair neutrality.** USDJPY-first but multi-pair-ready. No USDJPY-only hardcoding.

## 3. Layered model

```
Data layer          ← src/data/
Regime layer        ← src/regime/
Strategy layer      ← src/strategies/       (Candidate generators only)
Admission layer     ← src/admission/        (accept / reject / defer / resize / replace)
Execution / risk    ← src/execution/, src/risk/
Feedback loop       ← src/feedback/
```

All cross-layer traffic flows through `src/decision_path.py`. Strategies never talk to execution directly.

## 4. 3-gate evaluation

A strategy is **not** live until it passes all three:

1. **Standalone gate**: `avg_r > 0`, `pf ≥ 1.10`, `max_dd ≤ 0.30`, `trade_count ≥ 300`, positive-year-ratio ≥ 0.75.
2. **Marginal contribution gate**: `delta_pf > 0` on existing portfolio, `delta_max_dd` within allowance, `positive_year_ratio` not degraded, slot occupancy not worse.
3. **Shadow gate**: cost drift, missed fills, runtime stability, data freshness all within bounds over the shadow window.

Strong standalone + weak marginal contribution = rejected.

## 5. Personal-use simplification

We explicitly **keep**:

- Deterministic backtest evidence.
- Shadow / live parity.
- Kill switch, spread guard, emergency unwind.
- Minimal runbooks.
- Logs and config history sufficient for reproduction.

We explicitly **drop** (see `archive/governance/` for retired material):

- Multi-role approval flows (Product Owner / Ops / Risk Officer).
- Trader sign-off templates.
- Detailed audit bundle generation.
- Promotion / change-request paperwork.
- Heavy development-plan + update-log ceremony.
- v2 completion-check loops and `multi_pair_*` expansion ceremony.

If a proposed change reaches for any of these, the default answer is **no**.

## 6. Near-term roadmap

Work order is rigid:

1. **Phase 1** — clean skeleton: archive retired code, install this charter, stand up `src/contract.py` + CI gates (`test_contract`, `test_parity`, `test_cost`).
2. **Phase 2** — realistic cost model: wire `config/execution.yaml` into the backtest pipeline; add swap, weekend gap, slippage distribution. Existing PF numbers will drop — that is correct.
3. **Phase 3** — one real alpha hypothesis under the 3-gate evaluation. Only after Phase 2 passes.

Phase 3 is the only phase that plausibly affects whether we win. Phases 1–2 exist to stop Phase 3 from lying.

## 7. Related

- [CLAUDE.md](../CLAUDE.md) — agent charter
- [docs/invariants.md](invariants.md) — CI gate contracts
- [docs/architecture/fx_portfolio_operating_system.md](architecture/fx_portfolio_operating_system.md) — deeper background (retained as reference)

Last updated: 2026-04-15
