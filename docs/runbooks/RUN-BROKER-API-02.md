# RUN-BROKER-API-02: ブローカーAPI監視・レートリミット・フェイルオーバー

> **ACカバレッジ**: AC-03, AC-06, AC-32, NFR-02, NFR-05, NFR-19  
> **Runbook版数**: v0.3  
> **最終更新日**: 2026-01-24  
> **最終更新者**: Codex (Doc Maintainer)  
> **仕様参照**: detailed_design_fx_signal_tool_v1.md §81.1-§81.6, §84.1-§84.5  
> **関連メトリクス/ログ**: metrics/broker_api.jsonl, metrics/broker_rate_limit.jsonl, logs/events/broker_alerts.jsonl, logs/events/broker_failover.jsonl, reports/ops/broker_monitor_<date>.md  
> **関連CLI**: `tradectl broker monitor status/test/limit/report`, `tradectl broker order list/show/override/replay/export`, `tradectl emergency trigger`

## 1. 目的
- Broker APIの遅延・エラー・レート制限を検知し、Health/Runbook/Failover対応へ連携する。
- Opsが手順に沿って監視→検証→フェイルオーバー→復旧記録まで一貫して実施できるようにする。

## 2. トリガー
1. `broker.latency.critical` / `broker.error.rate_limit` アラート発生時。
2. `tradectl broker monitor status --alerts`で未対応アラートが検出された場合。
3. API接続のサンドボックス/紙運用切替タイミング（Cutover準備）。

## 3. 標準手順
1. **状態確認**  
   - `tradectl broker monitor status --alerts`でアラートを確認し、`failover_state`が`blocked`の場合は復旧が先行。
2. **疎通テスト**  
   - `tradectl broker monitor test --adapter sandbox`を実行し、`heartbeat`のレイテンシとエラー有無を記録。
3. **レート制限の調整**  
   - `tradectl broker monitor limit --burst <n> --sustained <n>`で閾値を調整し、`metrics/broker_rate_limit.jsonl`に反映を確認。
4. **フェイルオーバー実行**  
   - 重大アラート発生時は`tradectl emergency trigger --scenario api_failover --runbook RUN-BROKER-API-02`を実行し、Opsの手動運用へ切替。
5. **復旧レポート**  
   - `tradectl broker monitor report --window 4h`で`reports/ops/broker_monitor_<date>.md`を生成し、Ops署名を追記。

## Appendix A: エラーコード別対応（注文回復 / §84.3.1連携）
> DocOpsメモ: `config/brokers/error_map.yaml`の更新時は本セクションの表とステップを同期させること。Evidenceパスはテンプレの`<order_id>`を実際のIDに置換し、添付ファイル名は`<timestamp>_<summary>.{json,md}`で統一する。

| アンカー | 対応エラー | trigger_reason | 監査イベントID | 主要ステップ | Evidenceチェックリスト |
| --- | --- | --- | --- | --- | --- |
| <a id="RL-01"></a>RL-01 | `RATE_LIMIT_EXCEEDED` | `rate_limit` | `audit.order_recovery_planned.rate_limit` | 1. `tradectl broker rate-limit window --broker <name>`で残トークン確認<br>2. `tradectl broker orders override --order <id> --action retry --runbook-step RL-01`（自動再送1回目の場合のみ）<br>3. `StageGuard`を`partial_auto`以下へ調整し、低優先度注文の延期を記録 | - `rate_limit_window.json`を保存<br>- CLIログ（override実行）<br>- StageGuard変更記録スクリーンショット |
| <a id="TO-02"></a>TO-02 | `GATEWAY_TIMEOUT`/HTTP504 | `timeout` | `audit.order_recovery_planned.timeout` | 1. `tradectl emergency dispatch --plan api_retry --order <id>`を実行し、手順カードを確認<br>2. `EmergencyOrchestrator`の承認者（`ops_manager`）へ通知<br>3. 承認後に`tradectl broker orders override --order <id> --action retry --runbook-step TO-02` | - `orchestrator_plan.yaml`ダウンロード<br>- Approverチャットログ（スクリーンショット）<br>- 再送結果のCLIログ |
| <a id="PF-03"></a>PF-03 | `PARTIAL_FILL_STALE` | `partial_fill_timeout` | `audit.order_recovery_planned.partial_fill` | 1. `tradectl broker orders convert --order <id> --mode reduce-only`でReduce-Onlyチケット生成<br>2. HITLトレーダーへ承認依頼（`tradectl board notify --ticket <id>`）<br>3. FillShadow差分を確認し、未約定数量が解消されたことを検証 | - Reduce-OnlyチケットJSON<br>- トレーダー承認ログ<br>- FillShadow差分レポート |
| <a id="RJ-04"></a>RJ-04 | `ORDER_REJECT_COMPLIANCE` | `broker_reject` | `audit.order_recovery_planned.reject` | 1. `tradectl compliance explain --order <id>`で違反内容を抽出<br>2. `risk_policy.yaml`/`broker_rules.yaml`の該当項目を確認し、必要ならPOへエスカレーション<br>3. 修正案をRunbookコメントへ追記し、HITLで再入力 | - Compliance Explain出力（JSON）<br>- Policy Snapshot（該当行抜粋）<br>- 修正後注文の承認証跡 |
| <a id="AUTH-05"></a>AUTH-05 | `AUTH`/`PERMISSION` | `auth_failure` | `audit.order_recovery_planned.auth` | 1. `tradectl broker auth check --broker <name>`でキー有効性を確認<br>2. `config/broker_rules.yaml`とSecretsの更新履歴を確認し、鍵ローテーションを実施（`RUN-BROKER-AUTH-01`参照）<br>3. 影響注文の再送可否をPOと合意し、`tradectl broker orders override --order <id> --action manual --runbook-step AUTH-05`を実行 | - AuthチェックCLIログ<br>- Secretローテーション記録（Hash/時刻）<br>- 再送判断の合意ログ（チャットスクリーンショット） |
| <a id="UN-05"></a>UN-05 | `UNKNOWN`/その他 | `unknown_error` | `audit.order_recovery_planned.unknown` | 1. `EmergencyOrchestrator`で`api_investigate`プランを起動<br>2. `ops_manager`が`tradectl broker orders override --order <id> --action manual --runbook-step UN-05 --note "escalated"`を実行<br>3. ブローカーサポートへ問い合わせを起票し、SLAタイマーを設定 | - 原文レスポンス（JSON/raw）<br>- Opsエスカレーション記録（PagerDuty/Ticket）<br>- サポート問い合わせID |

## 4. 証跡・記録
- Evidenceは`evidence/broker/<order_id>/<category>/`配下に保存し、`EvidenceManifest`（`manifest.json`）へ以下を記録する。
  - `order_id`, `trigger_reason`, `runbook_ref`, `uploaded_by`, `uploaded_at`, `files`。
  - `files`は`[{"name": "rate_limit_window.json", "sha256": "..."}, ...]`の形式。
- `DocOps Orchestrator`はEvidenceパスとRunbook参照の整合性を毎朝`make check-validation --category broker_orders`で監査し、欠落があれば`ops.agenda.docops_pending`を生成する。

## 5. 更新フロー
1. `config/brokers/error_map.yaml`に新しいエラーコードが追加された場合、DocOpsは本Runbookの表・手順を更新し、`docs/development_plan.md#update-log-utc`へ記録する。
2. 更新後、`tradectl runbook verify --id RUN-BROKER-API-02`を実行して構文エラーが無いことを確認する。
3. Opsレビュー（ダブルサイン）完了後に`ops.agenda.docops_pending`をCloseし、Evidenceとして更新前後の差分（`git diff`）を添付する。

## 6. API注文ライフサイクル確認
1. **状態確認**  
   - `tradectl broker order list --status pending_ack --json`で滞留を確認。  
   - `queue_wait_ms`がSLOを超える場合は`RUN-BROKER-API-02#RL-01`へ移動。
2. **個別詳細**  
   - `tradectl broker order show --order <id> --include-history --json`で`recovery_plan`/`evidence_hash`を確認。
3. **Recovery操作**  
   - `tradectl broker order override --order <id> --action retry --runbook-step <RL-01|TO-02|PF-03|RJ-04|UN-05>`  
   - 手動対応の場合は`--action manual`と`--note`を必ず記録。
4. **照合完了**  
   - `OrderLifecycleManager.finalize()`相当の証跡が`audit.order_lifecycle_completed`へ記録されることを確認。
