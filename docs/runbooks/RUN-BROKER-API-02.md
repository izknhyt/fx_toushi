# RUN-BROKER-API-02: ブローカーAPI注文回復フロー

## 1. 目的
- API注文のライフサイクル中に発生する例外/遅延を安定的に処理し、Ops/トレーダーが手順に従って回復を完了できるようにする。
- `OrderLifecycleManager`が発行する`RecoveryPlan`と監査イベントをRunbook手順に紐付け、Evidenceの取得・保管を徹底する。

## 2. 前提条件
1. `tradectl broker orders list`で対象注文IDと`status`/`stage_guard_stage`を確認済み。
2. `SecureShareService`へのアップロード権限、および`ops_manager`または委任済み`ops_analyst`ロール。
3. `docs/runbooks/RUN-DATA-05.md`で定義されたデータSLAアラートが解消済み、もしくは`EmergencyOrchestrator`でAcceptable Degradation対応中であること。

## 3. 標準手順
1. `tradectl broker orders show --order <id> --include-history --include-evidence`で最新の`RecoveryPlan`と`error_context`を確認する。
2. `runbook_ref`に記載されたアンカー（本Runbook内の`#RL-01`等）へ移動し、該当手順を実施する。
3. 実施中は`ops.agenda.order_recovery`タスクのステータスを更新し、完了時にEvidenceパスを添付。
4. `tradectl broker orders override --order <id> --action {retry,manual}`を使用する際は、対応したRunbookステップIDを`--runbook-step`に指定する。
5. `SecureShareService`にEvidence（CLIログ/スクリーンショット/Policy Snapshot等）をアップロードし、URIを`RecoveryPlan.error_context.evidence_path`へ追記する。
6. 完了後に`tradectl broker orders replay --order <id> --compare-fill-shadow`でFill整合性を確認し、問題が無ければ`ops.agenda.order_recovery`をCloseする。

## 4. エラーコード別対応（§84.3.1連携）
> DocOpsメモ: `config/brokers/error_map.yaml`の更新時は本セクションの表とステップを同期させること。Evidenceパスはテンプレの`<order_id>`を実際のIDに置換し、添付ファイル名は`<timestamp>_<summary>.{json,md}`で統一する。

| アンカー | 対応エラー | trigger_reason | 監査イベントID | 主要ステップ | Evidenceチェックリスト |
| --- | --- | --- | --- | --- | --- |
| <a id="RL-01"></a>RL-01 | `RATE_LIMIT_EXCEEDED` | `rate_limit` | `audit.order_recovery_planned.rate_limit` | 1. `tradectl broker rate-limit window --broker <name>`で残トークン確認<br>2. `tradectl broker orders override --order <id> --action retry --runbook-step RL-01`（自動再送1回目の場合のみ）<br>3. `StageGuard`を`partial_auto`以下へ調整し、低優先度注文の延期を記録 | - `rate_limit_window.json`を保存<br>- CLIログ（override実行）<br>- StageGuard変更記録スクリーンショット |
| <a id="TO-02"></a>TO-02 | `GATEWAY_TIMEOUT`/HTTP504 | `timeout` | `audit.order_recovery_planned.timeout` | 1. `tradectl emergency dispatch --plan api_retry --order <id>`を実行し、手順カードを確認<br>2. `EmergencyOrchestrator`の承認者（`ops_manager`）へ通知<br>3. 承認後に`tradectl broker orders override --order <id> --action retry --runbook-step TO-02` | - `orchestrator_plan.yaml`ダウンロード<br>- Approverチャットログ（スクリーンショット）<br>- 再送結果のCLIログ |
| <a id="PF-03"></a>PF-03 | `PARTIAL_FILL_STALE` | `partial_fill_timeout` | `audit.order_recovery_planned.partial_fill` | 1. `tradectl broker orders convert --order <id> --mode reduce-only`でReduce-Onlyチケット生成<br>2. HITLトレーダーへ承認依頼（`tradectl board notify --ticket <id>`）<br>3. FillShadow差分を確認し、未約定数量が解消されたことを検証 | - Reduce-OnlyチケットJSON<br>- トレーダー承認ログ<br>- FillShadow差分レポート |
| <a id="RJ-04"></a>RJ-04 | `ORDER_REJECT_COMPLIANCE` | `broker_reject` | `audit.order_recovery_planned.reject` | 1. `tradectl compliance explain --order <id>`で違反内容を抽出<br>2. `risk_policy.yaml`/`broker_rules.yaml`の該当項目を確認し、必要ならPOへエスカレーション<br>3. 修正案をRunbookコメントへ追記し、HITLで再入力 | - Compliance Explain出力（JSON）<br>- Policy Snapshot（該当行抜粋）<br>- 修正後注文の承認証跡 |
| <a id="UN-05"></a>UN-05 | `UNKNOWN`/その他 | `unknown_error` | `audit.order_recovery_planned.unknown` | 1. `EmergencyOrchestrator`で`api_investigate`プランを起動<br>2. `ops_manager`が`tradectl broker orders override --order <id> --action manual --runbook-step UN-05 --note "escalated"`を実行<br>3. ブローカーサポートへ問い合わせを起票し、SLAタイマーを設定 | - 原文レスポンス（JSON/raw）<br>- Opsエスカレーション記録（PagerDuty/Ticket）<br>- サポート問い合わせID |

## 5. Evidence運用
- Evidenceは`evidence/broker/<order_id>/<category>/`配下に保存し、`EvidenceManifest`（`manifest.json`）へ以下を記録する。
  - `order_id`, `trigger_reason`, `runbook_ref`, `uploaded_by`, `uploaded_at`, `files`。
  - `files`は`[{"name": "rate_limit_window.json", "sha256": "..."}, ...]`の形式。
- `DocOps Orchestrator`はEvidenceパスとRunbook参照の整合性を毎朝`make check-validation --category broker_orders`で監査し、欠落があれば`ops.agenda.docops_pending`を生成する。

## 6. 更新フロー
1. `config/brokers/error_map.yaml`に新しいエラーコードが追加された場合、DocOpsは本Runbookの表・手順を更新し、`review_log.md`へ記録する。
2. 更新後、`tradectl runbook verify --id RUN-BROKER-API-02`を実行して構文エラーが無いことを確認する。
3. Opsレビュー（ダブルサイン）完了後に`ops.agenda.docops_pending`をCloseし、Evidenceとして更新前後の差分（`git diff`）を添付する。
