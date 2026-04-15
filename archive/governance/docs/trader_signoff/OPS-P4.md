# Trader Sign-off: OPS-P4（Ops Readiness Evidence Reset）

> **関連設計**: [詳細設計 §45 Ops証跡ガバナンス & スコアリセット制御](../../detailed_design_fx_signal_tool_v1.md#45-ops証跡ガバナンス--スコアリセット制御設計nfr-28-fr-63-ac-51)、[付録D.1 TR-30 Ops受入チェックシナリオ](../../detailed_design_fx_signal_tool_v1.md#付録d1-トレーダー受入チェックシナリオ)
>
> **Runbook連携**: `docs/runbooks/OPS-READINESS-01.md#sign-off`、`docs/runbooks/RUN-DATA-05.md#手順`、`docs/runbooks/RUN-POST-03.md#postmortem`

## 1. 目的
- Ops Readinessスコアのリセット条件（証跡欠損/期限切れ）を実演し、`ops_readiness_low`警告からの復旧プロセスをトレーダー視点で検証する。
- 証跡登録（`OpsEvidenceStore`）からValidation Data Playbook/Runbook連携までのエンドツーエンド手順をOps/Trader双方で再現し、NFR-28およびAC-51の監査要件を満たす。
- 再現結果を`reports/validation_log/ops_readiness_<YYYYWW>.md`と`reports/ops/evidence_audit/<YYYYMMDD>.md`に集約し、`logs/ops/review.log`のフォローアップとリンクさせる。

## 2. 対象スコープ
- Packet `OPS-P4`（`OpsReadinessService`と証跡リセット連携）に含まれる機能一式。
- `tests/integration/test_ops_readiness_evidence.py`で定義された`OpsEvidenceMissing`シナリオ（TR-30）とCLI経路。
- `config/ops_readiness.yaml`の`evidence_paths`および`runbook_refs`で参照される証跡/Runbook。

## 3. 関係者
- Ops Manager（主担当、CLI操作とRunbook整合確認）
- Trader Lead（実態確認、Board Guard挙動評価）
- Product Owner（Kill Switch解除判断、フォローアップ承認）
- Risk Manager（Reduce-Only解除可否レビュー）
- DocOps Liaison（Validation Log整形、Runbook更新チェック）

## 4. 前提条件
- [ ] `poetry run pytest -k ops_readiness_evidence` が成功し、最新リビジョンの`ops_readiness_score`挙動を確認済み。
- [ ] `make check-ops-readiness` 実行ログが`reports/validation_log/ops_readiness_<YYYYWW>.md#collection`に貼付済み。
- [ ] `docs/runbooks/OPS-READINESS-01.md#collect`／`#evidence-recovery`の必須チェックリストを完了し、`runbook_inventory_status.json`の該当項目が`status∈{ready,grace}`。
- [ ] データ復旧ルート: `docs/runbooks/RUN-DATA-05.md#手順`のReduce-Only運用と`docs/runbooks/RUN-POST-03.md#postmortem`で定義される事後レビュー準備が完了している。
- [ ] `reports/validation_log/ops_readiness_<YYYYWW>.md`ひな形（`reports/validation_log/templates/weekly.md`）から最新エントリを作成済み。

## 5. 具体的な受入手順
1. **証跡登録 (`RUN-DATA-05`/`OPS-READINESS-01`)**
   - `tradectl ops evidence add --category drill --runbook RUN-DATA-05 --artifact reports/ops/evidence_audit/<date>/backup_recovery.md --validation-playbook AC-45` を実行し、生成された`evidence_id`とSHA256を記録。
   - `ops_worklog.jsonl`へ`task="ops_evidence_add"`イベントが記録されたことを確認。
2. **Validation Data Playbook更新 (`OPS-READINESS-01`)**
   - `tradectl ops evidence sync --validation-playbook AC-45`で`reports/validation_log/AC-45_sla_<date>.md`に証跡が追記されたことを検証。
   - `reports/validation_log/ops_readiness_<YYYYWW>.md#score-sheet`へサブスコアとRunbook参照（`RUN-DATA-05#手順2`）を反映。
3. **期限切れシミュレーション (`OPS-READINESS-01#evidence-recovery`)**
   - `tradectl ops evidence expire --id <evidence_id> --reason "expiry_drill_simulation"` を実施し、`logs/health/events.jsonl`に`OpsEvidenceMissing`イベントが追記されたことを確認。
   - `config/ops_readiness.yaml`を再読込み (`make check-ops-readiness`) し、`missing_evidence`エントリが`reports/governance/ops_readiness_<YYYYWW>.json`に反映されたことを確認。
4. **Reduce-Only監視 (`RUN-DATA-05`)**
   - `tradectl status --json`で `ops.banner.runbook="docs/runbooks/OPS-READINESS-01.md"` および `board_mode="guarded"` を確認し、スクリーンショット/JSONを `docs/trader_signoff/OPS-P4/assets/status_guarded.json` に保存。
   - トレーダーは`tradectl board --guarded`の操作感を確認し、`ops_worklog`に操作時間を追加。
5. **是正と事後レビュー (`RUN-POST-03`)**
   - `OpsEvidenceStore.register`で新証跡を再登録し、`make check-ops-readiness`成功後に`tradectl health ack --reason ops_readiness_recovered`を実行。
   - `logs/ops/review.log`へ事後レビュー記録（`RUN-POST-03`フォーマット）を追記し、`reports/ops/evidence_audit/<YYYYMMDD>.md`にリンク。

## 6. 必要証跡一覧
| 分類 | ファイル/ログ | 内容 | 取得方法 |
| --- | --- | --- | --- |
| Validation | `reports/validation_log/ops_readiness_<YYYYWW>.md` | `Collection`/`Score Sheet`/`Sign-off`各節を埋め、Runbook参照を明記 | `reports/validation_log/templates/weekly.md`から複製、CLI結果を貼付 |
| Evidence Audit | `reports/ops/evidence_audit/<YYYYMMDD>.md` | 証跡登録・失効・再登録のタイムラインと`OpsEvidenceMissing`イベントID | `tradectl ops evidence`系列コマンドのログを追記 |
| Ops Logs | `logs/ops/review.log` | 事後レビューサマリとフォローアップタスクID | `RUN-POST-03`に従い手動追記 |
| Health Events | `logs/health/events.jsonl` | `OpsEvidenceMissing`/`ops_readiness_recovered`イベント | CLI操作後にJSON行をエクスポート |
| Ops Worklog | `ops_worklog.jsonl` | Evidence登録/Reduce-Only操作の工数記録 | `tradectl ops log add ...` |

## 7. サインオフ
| ロール | 氏名 | サイン（`<Initials> / <Org> <YYYY-MM-DD HH:MM JST>`） | 判定 |
| --- | --- | --- | --- |
| Ops Manager |  |  | approve / hold / reject |
| Trader Lead |  |  | approve / hold / reject |
| Product Owner |  |  | approve / hold / reject |
| Risk Manager |  |  | approve / hold / reject |

## 8. レビュー履歴
| 日付 | 更新内容 | レビュアー |
| --- | --- | --- |
| 2025-03-22 | 初版作成（Ops Readiness Evidence Resetリハーサル） | Codex Liaison |

## 9. フォローアップ
- [ ] `OpsEvidenceStore`の自動失効通知を`Scheduler`で検証（担当: ）
- [ ] `RUN-POST-03`更新内容をDocOpsへ共有（担当: ）
- [ ] 次回Ops Agenda（`docs/runbooks/daily_agenda/<date>.md`）へ改善項目を登録（担当: ）

