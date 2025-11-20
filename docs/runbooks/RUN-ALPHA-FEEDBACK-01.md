# RUN-ALPHA-FEEDBACK-01 — Alpha Feedback / Scoreboard Activation

## 目的
- `alpha.profit_loop_enabled`, `alpha.dynamic_sizing`, `alpha.playbook_override` をLiveプロファイルで有効化する。
- Profit Loopメトリクス (`metrics/profit_loop.jsonl`) とScoreboard Bridge/Alphaスナップショットを生成し、Watchlistフリーの状態を証跡化する。
- HitLトレーダー/PO/OpsのダブルサインでProfit Readinessレバー「Alpha Feedback & Scoreboard」を`ok`に更新する。

## 前提条件
1. `config/feature_flags.yaml` が最新であり、`alpha.*` FlagsがPaper soak済み。
2. `reports/execution/live_bridge_<date>.md` にPaper→Liveブリッジ演習ログが添付済（`RUN-HITL-01`, `RUN-BROKER-01`完了）。
3. `metrics/strategy_scores.jsonl` に当該戦略の最新スコア行が存在し、Spread Penalty/Decayが閾値内。
4. `tradectl alpha review --with-scoreboard` がExit code 0で完走できる（Bridge JSONが存在、Watchlist残数0）。

## 手順
1. **Feature Flag切替**
   - `tradectl config flags --profile live --set alpha.profit_loop_enabled=true --set alpha.dynamic_sizing=true --set alpha.playbook_override=true`
   - `git diff config/feature_flags.yaml` を確認し、`docs/change_requests/ALPHA-<date>.md` に貼り付ける。
2. **HITLセーフティ確認**
   - Signal Board/Tauriで`board_mode`が`normal`かつ`double_entry`のコメントが正しく保存されることをスクリーンショット化（`evidence/alpha_loop/hitl_<timestamp>.png`）。
   - `tradectl alpha preview --pair USDJPY --regime asia --target-band day15 --risk moderate --format json` を実行し、`alpha_profiles.yaml`のConviction閾値が反映されているか確認。
3. **Scoreboard Bridge実行**
   - `poetry run tradectl scoring bridge --week <YYYY-Www>` を実行。
   - 出力されたBridgeファイルを `scoreboard/bridge/<week>.json` に保存、`scoreboard/alpha/<week>.json`にも複製。
4. **Profit Loop Evidence更新**
   - `tradectl alpha review --with-scoreboard --strategy <id> --export evidence/alpha_loop/review_<date>.json`
   - `metrics/profit_loop.jsonl` 最新行に `mode="live"`, `board_mode`, `decision_latency_ms`, `feedback_cycle_minutes` が記録されていることを確認。
   - `reports/performance/profit_loop_daily.md` を更新し、Conviction Drift / RR Gap / Spread Penalty表を貼り替える。
5. **Profit Readiness反映**
   - `tradectl ops readiness --profit --lever "Alpha Feedback & Scoreboard" --set-lever ok --evidence scoreboard/alpha/<week>.json reports/performance/profit_loop_daily.md reports/performance/live_bridge_pnl_<range>.md`
   - `ops_worklog.jsonl` に `task="alpha_bridge"` エントリを追記。
6. **ダブルサイン**
   - Ops：`reports/performance/profit_loop_daily.md` のRunbook表に署名。
   - Trader/PO：`scoreboard/alpha/<week>.json` と `reports/performance/live_bridge_pnl_<range>.md` を確認し、Watchlist理由が空であることを明記。

## 出力/証跡
- `scoreboard/bridge/<week>.json`, `scoreboard/alpha/<week>.json`
- `reports/performance/profit_loop_daily.md`
- `reports/performance/live_bridge_pnl_<range>.md`
- `metrics/profit_readiness.jsonl` (`lever="Alpha Feedback & Scoreboard"`, status=`ok`)
- `ops_worklog.jsonl#alpha_bridge`

## ロールバック
1. `tradectl config flags --profile live --set alpha.profit_loop_enabled=false --set alpha.dynamic_sizing=false`
2. `tradectl alpha review --with-scoreboard` を再実行し、Evidence差分を`docs/change_requests/ALPHA-<date>.md`へ追記。
3. `record_readiness(... status="warning")` を記録し、`OpsAgendaService`にTODOを登録。
