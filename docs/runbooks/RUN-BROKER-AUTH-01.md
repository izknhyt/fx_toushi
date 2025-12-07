# RUN-BROKER-AUTH-01: ブローカー認証・権限エラー対応

> **参照**: [詳細設計 §84/§85](../../detailed_design_fx_signal_tool_v1.md#84-api注文ライフサイクルエラー回復設計fr-07fr-39fr-58-ac-03ac-06ac-32ac-41-nfr-02nfr-05nfr-19), `OrderLifecycleManager.classify_error(fatal)`
> **関連CLI**: `tradectl broker auth check`, `tradectl broker orders override`
> **証跡**: `metrics/broker_faults.jsonl`, `logs/broker/auth_<date>.jsonl`, `reports/validation_log/AC-03_broker_auth_<date>.md`

## 目的
- Brokerの認証/権限エラー（fatalクラス）を即時特定し、鍵ローテーションと注文再送判断を手順化する。
- Kill Switch/Board Modeとの連携を明示し、誤発注や停滞リスクを低減する。

## トリガー
| 条件 | 初動 |
| --- | --- |
| `simulate_fault`で`error_class=fatal` | 本Runbookを起動、StageGuardは変更なし |
| Brokerレスポンス`401/403` | `tradectl broker auth check`を実行 |
| Secrets更新や権限変更が発覚 | 直近注文を棚卸し、再送可否をPOと合意 |

## 手順
1. **鍵・権限の健全性確認**  
   - `tradectl broker auth check --broker <name>`を実行し、結果を`logs/broker/auth_<date>.jsonl`へ保存。  
   - 直近のSecretローテーション記録と`config/broker_rules.yaml`のバージョンを突合。
2. **Kill Switch/Board Mode判断**  
   - 重大な権限喪失の場合、`tradectl kill-switch set --state hard_stop --reason auth_failure`を検討し、Board Modeを`halted`へ。  
   - Acceptable Degradation状態なら`RUN-OPS-AGENDA-01`の解除チェックを停止。
3. **修復・再送可否の決定**  
   - キー再発行後、テスト注文でACKが通ることを確認。  
   - 影響注文を`tradectl broker orders override --order <id> --action manual --runbook-step AUTH-05 --note "auth recovered"`で処理。
4. **Evidenceと監査**  
   - `metrics/broker_faults.jsonl`にシナリオ/エラー分類が記録されていることを確認。  
   - `reports/validation_log/AC-03_broker_auth_<date>.md`へCLIログ・キー更新記録・再送判断を貼付。

## エスカレーション
- 30分以内にACK不可ならBrokerサポートへ問い合わせを起票し、`ops.agenda.docops_pending`へリンク。
- 再発時は`RUN-BROKER-API-02#RL-01`のRate Limit対策も再確認。

## 関連Runbook
- [RUN-BROKER-API-02](RUN-BROKER-API-02.md)
- [RUN-OPS-AGENDA-01](RUN-OPS-AGENDA-01.md)
