# RUN-BROKER-API-03: ブローカー・コンプライアンス調査 & リカバリ

> **Runbook版数**: v0.3  
> **最終更新日**: 2026-01-24  
> **最終更新者**: Codex (Doc Maintainer)  
> **参照**: [詳細設計 §84 API注文ライフサイクル](../../detailed_design_fx_signal_tool_v1.md#84-api注文ライフサイクルエラー回復設計fr-07fr-39fr-58-ac-03ac-06ac-32ac-41-nfr-02nfr-05nfr-19), [§85 フォールトインジェクション](../../detailed_design_fx_signal_tool_v1.md#85-apiフォールトインジェクション演習ラボfr-47fr-63-ac-34ac-43-nfr-02nfr-28), [§7 エラーハンドリング表 ERROR-B03](../../detailed_design_fx_signal_tool_v1.md#7-エラーハンドリング--フェイルセーフ)
>
> **関連CLI**: `tradectl broker compliance`, `tradectl broker orders`, `tradectl ops agenda`, `tradectl emergency close-all`
>
> **証跡**: `reports/execution/live_bridge_<date>.md`, `metrics/broker_orders.jsonl`, `logs/broker/compliance_<date>.jsonl`

## 目的
- Broker API側からのコンプライアンス拒否/約定制限・証跡要求へ迅速に対応し、OrderLifecycleの追跡とKill Switch判断を連携させる。
- Ops/トレーダー/リスクが同じRunbookを参照し、`AC-41`および`NFR-17`の監査要件を満たす。

## トリガー
| 種別 | 条件 | 初動 |
| --- | --- | --- |
| 自動 | `broker_compliance_reject`イベント | Step1から即時実行 |
| 自動 | `OrderLifecycleManager`が`stage=rejected`かつ`reason=compliance_flagged` | Step2へ |
| 手動 | Broker担当からメール/電話で再調査依頼 | Ops ManagerがRunbook起動を宣言 |

## 手順
1. **イベント確認**  
   - `tradectl broker orders --status rejected --since 24h`を実行し、対象注文を抽出。  
   - `logs/broker/compliance_<date>.jsonl`へCLI出力を保存。`order_id`と`broker_ticket_id`を特定。
2. **証跡収集**  
   - `tradectl broker compliance --order-id <id>`でBrokerから要求されたフィールド（KYC、用途、過去取引など）を確認。  
   - `reports/execution/live_bridge_<date>.md`に該当セクションを追記。
3. **Runbook連携**  
   - Spread起因の拒否の可能性がある場合は`RUN-RISK-03`へリンクし、Board Modeを`guarded`に設定。  
   - Rate Limit/リトライが必要な場合は`RUN-BROKER-API-02#RL-01`を参照。
4. **Opsタスク生成**  
   - `OpsAgendaService.create_item(task="broker_compliance_review", due=<date+1d>)`をCLI `tradectl ops agenda --add`で登録。  
   - `docs/runbooks/daily_agenda/<date>.md`にRunbook IDと担当者を追記。
5. **修正/再送**  
   - Broker指定の修正（例: 発注サイズ、口座モード）を`config/profiles/<mode>.yaml`へ反映し、`poetry run schema-validate`で検証。  
   - 再送信は`tradectl broker orders --retry <order_id>`を利用し、`metrics/broker_orders.jsonl`の`stage=submit→ack`がSLA内か確認。
6. **承認・記録**  
   - Ops Managerが`reports/validation_log/AC-41_<date>.md`に対応ログを追記。  
   - Trader Leadが`docs/trader_signoff/<packet>.md`の`Broker Compliance`欄に結果を記入。

## エスカレーション
- 2時間以内にBroker側確認が取れない場合は`RUN-EMER-UNWIND-01`の`Close-All`ステップを準備。
- コンプライアンス改善策が必要な場合は`RUN-GOV-BOARD-01`へエントリを追加し、Configレビューを即時開始。

## 証跡要求リスト
| 種別 | 保存先 | 備考 |
| --- | --- | --- |
| Brokerリクエストメール | `evidence/broker/<order_id>/request.eml` | 署名・タイムスタンプ必須 |
| CLIログ | `reports/execution/live_bridge_<date>.md` | `tradectl broker compliance`のstdoutをコピー |
| OrderLifecycle JSON | `reports/execution/order_<order_id>.json` | `docs/schemas/order_state.schema.json`準拠 |

## 関連Runbook
- [RUN-BROKER-API-02](RUN-BROKER-API-02.md)
- [RUN-RISK-03](RUN-RISK-03.md)
- [RUN-EMER-UNWIND-01](RUN-EMER-UNWIND-01.md)

## Cutover/認定連携
- 認定実行: `tradectl broker certify --plan config/certification/sandbox.yaml --report-dir reports/validation_log`
- Cutoverチェック: `tradectl release cutover broker --profile paper --version <release>`
- 未達項目がある場合は `tradectl release cutover verify --profile paper --version <release>` が Exit code 86 で失敗するため、Ops/Complianceで対応を完了させる。

## Autonomy StageGuard（段階的自動化）
1. **ステージ確認**  
   - `tradectl broker stage status --json` で現在ステージとブロック理由を確認。  
   - `pending_requests` がある場合は `tradectl supervision status` で承認待ち一覧を確認。
2. **ステージ申請**  
   - `tradectl broker stage request --stage reduce_only --reason "cert pass"` で申請。  
   - Ops Managerが `tradectl supervision approve --request-id <id> --actor ops_manager` を実行。
3. **降格対応**  
   - Emergency/Fault発生時は `tradectl broker stage set --stage manual_only --approve ops_manager` で即時降格。  
   - 降格後は `BrokerCertificationSuite` 再実行が必要。

## Supervision Console
- `tradectl supervision status` にて以下を確認。  
  - `autonomy_stage`: 現在ステージと次遷移条件  
  - `ops_readiness`: readinessスコア推移  
  - `emergency_status`: Failover状態  
  - `audit_trail`: Stage変更/緊急プランの履歴
