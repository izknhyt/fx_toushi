# RUN-RISK-03: Spread/Pre-Trade異常ハードエンフォースメント

> **参照**: [詳細設計 §3.5 StrategyEngine](../../detailed_design_fx_signal_tool_v1.md#35-strategyengine-srcstrategiesregistrypy), [§3.6 ExecutionModel](../../detailed_design_fx_signal_tool_v1.md#36-executionmodel-srcexecutionmodelpy), [§64/§71 ストレスラボ](../../detailed_design_fx_signal_tool_v1.md#64-マージン相関ストレスラボとリスクエンベロープ調整fr-36fr-37fr-51-ac-32)
>
> **関連設定**: `config/risk_policy.yaml`, `config/reduce_only.yaml`, `config/board_modes.yaml`
>
> **イベント**: `health.raise('major','spread_guard')`, `gate_state.market.spread.state != 'normal'`, `OpsAgendaService.task='pretrade_guard'`

## 目的
- Spread/Latency/Pre-Tradeコンプライアンス違反を検知後、Board Mode・Kill Switch・ダブルエントリーを統制し、証跡をAC-32/AC-45要件に沿って残す。
- Trader承認とOps実務を同期させ、Reduce-Only/Close-Allなどの対策を迅速に適用する。

## トリガー
| 種別 | 条件 | 初動 |
| --- | --- | --- |
| 自動 | `GateState.market.spread.state ∈ {cooldown, halt}` | 即時に本Runbookを開き、Step1〜2を実行 |
| 自動 | `ExecutionModelInputError(spread_state=None)` 連続3回 | `RUN-CORR-02`との整合を確認後、本RunbookStep3へ |
| 手動 | トレーダーが`tradectl board`上でSpread警告を確認 | Step1で再現ログを取得 |

## 手順
1. **状態取得**  
   - `tradectl board --view risk --json`を実行し、`GateState`抜粋を`reports/risk/spread_incident_<timestamp>.json`へ保存。  
   - `docs/schemas/gate_state.sample.json`とdiffを取り、フィールド欠落がないか確認。
2. **CLIエビデンス**  
   - `tradectl execution bridge-log --mode <paper|live> --stage paper_live_bridge`で`metrics/execution_bridge.jsonl`を更新し、Spread異常によるレイテンシ/Rejectを確認。  
   - `reports/ops/edge_watch_<week>.md`に抜粋を貼付。
3. **ダブルエントリー強制**  
   - `config/reduce_only.yaml`の`human_gate.double_ack_roles`と一致するメンバーで`tradectl ticket approve --double-entry-user <...>`を実行。  
   - コメントは`human_gate.comment_min_length`以上で、RunbookID(`RUN-RISK-03#step3`)を含める。
4. **Board Mode/Reduce-Only判定**  
   - Spreadが`halt`の場合はKill Switchを`stop`へ（`tradectl kill-switch stop`）。  
   - `ops_worklog.jsonl`へ`{"task":"reduce_only","minutes":<min>,"meta":{"runbook":"RUN-RISK-03"}}`を追記。
5. **ブローカー連携**  
   - Broker起因の拒否が疑われる場合は`RUN-BROKER-API-03`でコンプライアンス状況を確認。  
   - 追加で`RUN-BROKER-API-02`（RateLimit/Retry）を必要に応じて実施。
6. **解除判定**  
   - 連続2バーで`GateState.market.spread.state == 'normal'`を確認後、Board Modeを`normal`へ戻し、`RUN-GOV-BOARD-01`で承認記録。  
   - `reports/validation_log/AC-32_<date>.md`へ対応結果を追記。

## エスカレーション
- 60分以内にSpreadが回復しない場合は`RUN-EMER-UNWIND-01`の`Reduce-Only`ステップを実施。
- バックテストとの差分が疑われる場合は`STRAT-M1-VALIDATION`で再現手順を走らせ、`AC-01`証跡を更新。

## 証跡・記録
- `logs/audit/ticket_actions_*.jsonl`へ`ticket.checklist.ack`イベントが二重記録されたことを確認。
- `reports/risk/reduce_only_<date>.md`に本Runbookの実施ログとSpread/Latency指標を記載。
- OpsとTraderの署名を`docs/trader_signoff/<packet>.md`「Spread Guard」欄に追加。

## 関連Runbook
- [RUN-CORR-02](RUN-CORR-02.md)
- [RUN-GOV-BOARD-01](RUN-GOV-BOARD-01.md)
- [RUN-BROKER-API-02](RUN-BROKER-API-02.md)
- [RUN-BROKER-API-03](RUN-BROKER-API-03.md)
