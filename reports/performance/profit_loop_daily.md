# Profit Loop Daily Snapshot — 2025-12-19 (Week 2025-W13)

- Generated At: 2025-11-20T11:41:01Z (`poetry run tradectl scoring bridge --week 2025-W13 --mode live`)
- Sources: `scoreboard/bridge/2025-W13.json`, `metrics/profit_loop.jsonl`, `reports/performance/live_bridge_pnl_20251119-20251219.md`
- Scoreboard Alpha Export: `scoreboard/alpha/2025-W13.json`
- Profit Readiness CLI Snapshot: `poetry run tradectl ops readiness --profit --lever "Alpha Feedback & Scoreboard" --json`
- Related Commands:
  - `tradectl alpha review --date 2025-12-19 --with-scoreboard --strategy m1_baseline_ma_rsi`
  - `tradectl ops readiness --profit --lever "Alpha Feedback & Scoreboard" --set-lever ok --evidence scoreboard/alpha/2025-W13.json reports/performance/live_bridge_pnl_20251119-20251219.md`

## Strategy Metrics (Bridge.v1)

| Strategy | Alpha Score | Decay Score | Conviction Drift | RR Gap | Spread Penalty | Status | Watchlist Reasons | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `m1_baseline_ma_rsi` | 84 | 18 | +0.06 | +0.06 | 0.02 | ok | - | `scoreboard/bridge/2025-W13.json`, `reports/execution/live_bridge_20251219.md` |

### m1_baseline_ma_rsi

- Ops review: Conviction drift +0.06, Spread Penalty 0.02（Market Edgeレバー閾値内）。
- Feedback cycle: p90 8h (`metrics/profit_loop.jsonl` 2025-11-20〜12-19, mode=live)。`evidence/alpha_loop/review_20251219.json`を参照。
- Watchlist: **解除**。`RUN-GOV-BOARD-01`でWatchlistフラグ無しを確認し、Profit Readinessレバーを`ok`に更新。

## Runbook Checklist & Sign-off

| Runbook | Step | 状態 | サイン |
| --- | --- | --- | --- |
| `RUN-ALPHA-FEEDBACK-01` | Alpha feature flag enable + evidence export | ✅ 完了 | Ops: `codex_ops` (2025-12-19 15:00Z) |
| `RUN-GOV-BOARD-01` | Scoreboard review / watchlist判断 | ✅ 完了 | Trader: `codex_trader` (2025-12-19 15:05Z) |
| `RUN-SPREAD-03` / `RUN-CORR-02` | Edge Watch / guard確認（Profit Loop連動） | ✅ 完了 | Ops/Risk: `codex_ops` / `codex_risk` |

> Evidence Links: `reports/performance/live_bridge_pnl_20251119-20251219.md`, `scoreboard/bridge/2025-W13.json`, `scoreboard/alpha/2025-W13.json`, `reports/execution/live_bridge_20251219.md`.

---

## Historical Snapshot — 2025-11-19 (Week 2025-W12)

- Generated At: 2025-11-19T14:13:57Z (`poetry run tradectl scoring bridge --week 2025-W12`)
- Sources: `scoreboard/bridge/2025-W12.json`, `metrics/profit_loop.jsonl`
- Scoreboard Alpha Export: `scoreboard/alpha/2025-W12.json`
- Related Commands:
  - `tradectl alpha review --date 2025-11-19 --with-scoreboard --strategy m1_baseline_ma_rsi`
  - `poetry run tradectl spread guard --symbol USDJPY --simulate --attach reports/ops/edge_watch_2025-W12.md`

| Strategy | Alpha Score | Decay Score | Conviction Drift | RR Gap | Spread Penalty | Status | Watchlist Reasons | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `m1_baseline_ma_rsi` | 68 | 21 | -0.09 | -0.09 | 0.04 | alert | alpha_below_threshold | `scoreboard/bridge/2025-W12.json` |

- Ops review: Conviction driftとRR Gapが -0.09で一致。Spreadペナルティは0.04（guarded維持）。
- Feedback cycle: ≤24h（RUN-ALPHA-FEEDBACK-01 Step 4で確認済）。`tradectl alpha review`結果は `evidence/alpha_loop/review_20251119.json` に保存。
- Watchlist: `RUN-GOV-BOARD-01`で継続承認（理由: `alpha_below_threshold`）。改善アクションはEdge Watchレポート（2025-W12）を参照。

| Runbook | Step | 状態 | サイン |
| --- | --- | --- | --- |
| `RUN-ALPHA-FEEDBACK-01` | Feedback loop validation & evidence export | ✅ 完了 | Ops: `codex_ops` (2025-11-19 14:20Z) |
| `RUN-GOV-BOARD-01` | Scoreboard review / watchlist判断 | ✅ 完了 | Trader: `codex_trader` (2025-11-19 14:25Z) |
| `RUN-SPREAD-03` / `RUN-CORR-02` | Edge Watch / guard確認（Profit Loop連動） | ✅ 完了 | Ops/Risk: `codex_ops` / `codex_risk` |

> Evidence Links: `reports/ops/edge_watch_2025-W12.md`, `scoreboard/bridge/2025-W12.json`, `evidence/alpha_loop/review_20251119.json`.
