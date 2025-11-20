# RUN-GOV-BOARD-01: Strategy Scoreboard & Board Modeレビュー

> **参照**: [詳細設計 §3.25 Scoreboard](../../detailed_design_fx_signal_tool_v1.md#325-scoreboard-service), [§7.6 週次レポート](../../detailed_design_fx_signal_tool_v1.md#76-週次レポート受入条件), [§0.6.14 Profit Readiness](../../detailed_design_fx_signal_tool_v1.md#0614-プロフィット実現準備サマリ)
>
> **関連設定**: `config/scoreboard.yaml`, `config/board_modes.yaml`
>
> **成果物**: `reports/performance/profit_loop_daily.md`, `scoreboard/alpha/<week>.json`, `reports/weekly/evidence/<YYYY-WW>/`

## 目的
- Strategy ScoreboardとSignal Boardの状態を週次でレビューし、Board Mode/Runbook間の整合を確認する。
- Trader/POが同じ証跡セットを参照して承認できるよう、CLIスナップショットとScoreboard JSONを標準化する。

## トリガー
- 週次Opsレビュー（通常は月曜午前）で必ず実施。
- Board Modeが`guarded`または`halted`へ遷移した場合は臨時レビューフローを即時起動。

## 事前準備
1. `poetry run schema-validate config/scoreboard.yaml --schema docs/schemas/scoreboard.schema.json`を実行し、成功ログを保存。
2. `docs/schemas/gate_state.sample.json`と現行`snapshots/latest/gate_state.json`をdiffし、差異がないことを確認。
3. `reports/ops/edge_watch_<week>.md`・`metrics/profit_readiness.jsonl`を取得し、更新日時を控える。

## 手順
1. **Scoreboard生成**  
   `tradectl scoring bridge --week <YYYY-WW> --out scoreboard/alpha/<YYYY-WW>.json`を実行。CLI出力を`reports/weekly/evidence/<YYYY-WW>/scoreboard_bridge.log`へ保存。
2. **Signal Boardスナップショット**  
   `tradectl board --view strategy --save-snapshot reports/weekly/evidence/<YYYY-WW>/board_snapshot.json`を実施。`GateState.market`/`risk.reduce_only`の状態をチェック。
3. **Runbook照合**  
   - Market Edgeに関与するアラートは`RUN-CORR-02`、Reduce-Only判定は`RUN-RISK-02`の証跡リンクを確認。
   - Ticket承認のダブルエントリー状況は`RUN-RISK-03`に準拠しているかを`logs/audit/ticket_actions_*.jsonl`で確認。
4. **レビュー記録**  
   `reports/governance/strategy_board/<YYYY-WW>.md`のテンプレに以下を記入:  
   - Scoreboard要約（Top3戦略、Conviction vs 実績）  
   - GateState差分（`docs/schemas/gate_state.sample.json`基準）  
   - ボードモード決定とRunbook ID（例:`RUN-CORR-02#step5`）
5. **承認**  
   - Trader Leadが`docs/trader_signoff/<packet>.md`に`scoreboard_snapshot`リンクを追記。  
   - POが`reports/weekly/evidence/<YYYY-WW>/board_snapshot.json`に署名ハッシュを記入。  
   - Ops Managerが`ops_worklog.jsonl`へ task=`strategy_board_review` を記録。

## エスカレーション
- Scoreboardで`alpha_score<thresholds.alpha`または`decay_score>thresholds.decay`の場合、`OpsAgendaService`へ`task='profit_readiness'`を追加し、`RUN-OPS-AGENDA-01`を通じてトリアージ。
- Board Modeが3日以上`guarded`の場合は`RUN-EMER-UNWIND-01`の準備チェックを実施。

## 証跡
- `reports/validation_log/AC-45_sla_<date>.md`にScoreboard/Board CLIログのパスとSHA256を記載。
- `reports/performance/profit_loop_daily.md`に当日の判断とRunbook IDを追記。

## 関連Runbook
- [RUN-CORR-02](RUN-CORR-02.md)
- [RUN-RISK-02](RUN-RISK-02.md)
- [RUN-OPS-AGENDA-01](RUN-OPS-AGENDA-01.md)
