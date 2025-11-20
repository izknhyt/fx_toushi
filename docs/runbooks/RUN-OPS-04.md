# RUN-OPS-04: 外部イベント遮断・解除手順

> **参照**: [詳細設計 §3.13 CalendarService](../../detailed_design_fx_signal_tool_v1.md#313-calendarservice-srccalendarservicepy), [§3.5 StrategyEngine GateState](../../detailed_design_fx_signal_tool_v1.md#35-strategyengine-srcstrategiesregistrypy), [§0.6.14 Profit Readiness](../../detailed_design_fx_signal_tool_v1.md#0614-プロフィット実現準備サマリ)
>
> **関連設定**: `config/calendar/events.csv`, `config/board_modes.yaml`, `config/reduce_only.yaml`
>
> **証跡**: `logs/events/calendar_block.jsonl`, `docs/schemas/gate_state.sample.json`, `reports/ops/calendar_block_<date>.md`

## 目的
- FOMC/雇用統計など外部イベント時にSignal Boardを安全に停止し、解除後の再開までを一貫した証跡で管理する。
- `GateState.market.per_symbol`と`OpsAgenda`を同期させ、トレーダー・Opsが同じ情報で判断する。

## トリガー
| イベント | 例 | 期限 |
| --- | --- | --- |
| 予定イベント | FOMC、BoJ、ECB、米雇用統計、月末Fix | 24時間前までにブロック設定 |
| 臨時イベント | 重大ニュース、地政学リスク | Ops Manager判断後即時 |

## 事前準備
1. `CalendarService`の最新データを`tradectl data calendar --sync`で更新し、`logs/calendar_sync.log`を確認。
2. `docs/schemas/gate_state.sample.json`を開き、`market.calendar`/`market.per_symbol[*].calendar`の例と比較。
3. 該当Runbook（`RUN-CORR-02`, `RUN-GOV-BOARD-01`）の最新証跡を確認し、既存ブロックがないか確認。

## 手順
1. **ブロック計画**  
   - `tools/calendar_block_plan.py --event <name> --symbols <pairs> --window <start,end>`でブロック案を生成し、`reports/ops/calendar_block_<date>.md`へ保存。
2. **GateState反映**  
   - `tradectl calendar block --event <name> --start <ts> --end <ts> --symbols <pairs>`を実行。  
   - `GateAggregator.snapshot()`が`docs/schemas/gate_state.schema.json`に適合し、`per_symbol`へ記録されたことを`logs/audit/gate_refresh.log`で確認。
3. **Board通知**  
   - `tradectl board --view risk`で`calendar.blocked`が表示されているかスクリーンショット取得。  
   - `RUN-GOV-BOARD-01`のチェックリストに添付。
4. **Ops Agenda更新**  
   - `tradectl ops agenda --date <date> --append "Calendar block <event>"`でTODOを挿入。  
   - `docs/runbooks/daily_agenda/<date>.md`の`Critical First`にRunbook IDを追記。
5. **解除判定**  
   - イベント終了後、`tradectl calendar unblock --event <name>`を実行。  
   - Spread/Correlation異常が無ければ`RUN-CORR-02`の観測結果を引用し、Board Modeを`normal`へ戻す。
6. **証跡保管**  
   - `reports/validation_log/AC-05_ingestion_perf_<date>.md`へブロック/解除時のCLIログとGateStateハッシュを記録。

## エスカレーション
- ブロック解除後に`GateState.market.spread.state != normal`の場合は`RUN-RISK-03`を開始し、Kill Switch評価を行う。
- 外部API遅延でブロック反映に失敗した場合は`RUN-BROKER-API-02`/`RUN-BROKER-API-03`でフォロー。

## 記録
- Ops作業ログ: `tradectl ops log add --task calendar_block --duration <min> --notes "RUN-OPS-04#<event>"`。
- Trader承認: `docs/trader_signoff/<packet>.md`の`Event Block`欄に結果を記載。

## 関連Runbook
- [RUN-CORR-02](RUN-CORR-02.md)
- [RUN-GOV-BOARD-01](RUN-GOV-BOARD-01.md)
- [RUN-RISK-02](RUN-RISK-02.md)
