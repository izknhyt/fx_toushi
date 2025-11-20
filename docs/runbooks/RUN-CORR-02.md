# RUN-CORR-02: 相関ガード監視・手動是正

> **参照**: [詳細設計 §64 マージン・相関ストレスラボ](../../detailed_design_fx_signal_tool_v1.md#64-マージン相関ストレスラボとリスクエンベロープ調整fr-36fr-37fr-51-ac-32), [§71 Hardening検証ハーネス](../../detailed_design_fx_signal_tool_v1.md#71-hardening検証ハーネス診断ラボ群), [§0.6.14 Market Edge Protection](../../detailed_design_fx_signal_tool_v1.md#0614-プロフィット実現準備サマリ)
>
> **関連CLI**: `tradectl spread guard`, `tradectl correlation guard`, `tradectl ops agenda`
>
> **証跡**: `reports/ops/edge_watch_<week>.md`, `metrics/spread_guard.jsonl`, `reports/validation_log/AC-32_<date>.md`

## 目的
- スプレッド急拡大や相関崩壊をBacktest/Paper/Liveで同一閾値に基づき検知し、提案抑止やReduce-Only切替を遅滞なく実施する。
- Ops/トレーダー双方で根拠を共有し、§64/§71で定義されたストレスラボ証跡を維持する。

## トリガー
| 種別 | 条件 | アクション種別 |
| --- | --- | --- |
| 自動 | `metrics/spread_guard.jsonl`で`state ∈ {cooldown, halt}`が連続3回 | 即時でBoardModeを`guarded`へ提案、Reduce-Only Advisorを検討 |
| 自動 | `metrics/correlation_guard.jsonl`の`bucket_violation_count>0` | Runbook本手順に従いヒューマン承認 |
| 手動 | トレーダーが板状況/市場イベントで逸脱を感知 | CLI `tradectl correlation guard --simulate`で証跡採取 |

## 事前準備
1. 最新の`config/risk_policy.yaml`と`config/broker_rules.yaml`をPullし、`sha256sum`をOpsチャンネルへ共有。
2. `docs/schemas/gate_state.sample.json`を開き、`market.spread`/`per_symbol[*].spread`の状態を確認。
3. `RUN-SPREAD-03`の結果ログと照合し、既に手動対応中かどうかを把握。

## 手順
1. **現状確認**: `tradectl spread guard --symbol <pair> --simulate`で通常/guarded/reduce-onlyの3パターンを取得し、`reports/ops/edge_watch_<week>.md`へ貼付。
2. **相関評価**: `tradectl correlation guard --pairs <pairA,pairB>` を実行し、`bucket`逸脱値と推奨行動を確認。逸脱`> config/risk_policy.correlation.max_delta`の場合はReduce-Only推奨。
3. **GateState更新**: `tools/ops_update_gate.py --spread-state <state> --symbols <...>` を実行し、`GateAggregator`が`docs/schemas/gate_state.schema.json`に準拠したスナップショットを生成したことを`logs/audit/gate_refresh.log`で確認。
4. **Board通知**: `tradectl board --guarded`のスクリーンショットを取得し、`RUN-GOV-BOARD-01`のチェックリストに添付。
5. **Runbook連携**: Reduce-Onlyへ移行する場合は`RUN-RISK-02#step4`を開始し、Ops/POダブルACKを`ops_worklog.jsonl`へ追記。
6. **証跡更新**: `metrics/spread_guard.jsonl`と`reports/ops/edge_watch_<week>.md`のハッシュを`reports/validation_log/AC-32_<date>.md`へ記載。

## エスカレーション
- 30分以内にSpread状態が`normal`へ戻らない場合は`RUN-RISK-03`を起動し、Kill Switch検討へ進む。
- Broker由来のスプレッド異常が疑われる場合は`RUN-BROKER-API-03`を参照し、ステートメント照合とAPI制限を確認。

## 記録
- Ops作業: `tradectl ops log add --task spread_guard --duration <min> --notes "RUN-CORR-02#<symbol>"`。
- トレーダー承認: `docs/trader_signoff/<packet>.md`の`Market Edge`欄に対応内容を記入。

## 関連Runbook
- [RUN-SPREAD-03](RUN-SPREAD-03.md)
- [RUN-RISK-02](RUN-RISK-02.md)
- [RUN-GOV-BOARD-01](RUN-GOV-BOARD-01.md)
