# RUN-AUD-02: ブローカーステートメント突合手順

> **ACカバレッジ**: FR-64, AC-53  
> **Runbook版数**: v1.0  
> **最終更新日**: 2025-11-03  
> **最終更新者**: Back Office Lead (Doc Maintainer)  
> **仕様参照**: detailed_design_fx_signal_tool_v1.md §25.1-25.4, §30.1-30.2; basic_design_fx_signal_tool_v1.md:121,208,273; 要件定義（テンプレ形式）v_1.md:188  
> **運用シナリオID**: TR-14 (Statement reconciliation drill)  
> **関連メトリクス/ログ**: metrics/reconciliation.jsonl, logs/audit/reconciliation_*.jsonl, reports/audit/reconciliation/<date>_<broker>.md, reports/audit/audit_pack/<period>.md, validation_playbook/AC-64_reconciliation.md  
> **外部資料**: statement_reconciliation.yaml, docs/templates/reconciliation_report.md, reports/governance/runbook_inventory_status.json, docs/runbooks/RUN-REC-02.md, docs/runbooks/RUN-TAX-01.md

## 目的
- ブローカー公式ステートメントを`StatementReconciliationService`で正規化し、約定ログと突合して差分を明確化・是正する。
- 差分が閾値を超えた場合はReduce-Only/Kill Switch判断や税務・監査準備に直結するフォローアップ (`RUN-REC-02`, `RUN-TAX-01`) を開始する。
- 突合結果と証跡を`reports/audit/reconciliation/<date>_<broker>.md`に集約し、Validation Data PlaybookとCI (`make check-runbooks`, `make check-validation`) の判定に利用する。

## トリガー
- `tradectl reconcile statements --from <date>`ジョブが`match_rate<config.reconciliation.threshold.match`または`balance_diff>|config.reconciliation.threshold.balance|`で終了したとき。
- `metrics/reconciliation.jsonl`に`match_rate<0.99`、`balance_diff>0.5R`、`swap_diff≠0`が記録されたとき。
- Back Officeが新しい月次/四半期ステートメントを受領したとき。
- Ops AgendaまたはRunbookインベントリで本Runbookが`status=grace/overdue`になったとき。

## 責務
- **Back Office Lead**: ステートメント取得と正規化、突合実行、報告書作成。
- **Ops Manager**: CLI実行結果のレビュー、監査ログ・Evidence格納、Ops Worklog更新。
- **Risk Manager**: 差分がリスク閾値に影響するか評価し、Kill Switch/Reduce-Only判断へ連携。
- **Product Owner**: 重大逸脱時の承認/是正計画承認。

## 手順
1. **ステートメント取得とテンプレ準備**
   - ブローカーから受領したステートメントを`data/statement/<broker>/<YYYYMMDD>/`へ配置。PDFの場合は事前に`tools/pdf_to_csv.py`でCSVへ変換。
   - `statement_reconciliation/<broker>.yaml`を確認し、日付/タイムゾーン/丸め規則が最新であることを検証。差分がある場合はPRでテンプレ更新。
2. **突合実行**
   - CLIを実行し、MarkdownとJSONを同時出力する。
     ```console
     tradectl reconcile statements \
       --from 2025-10-01 --to 2025-10-31 \
       --broker <broker_id> \
       --statement-dir data/statement/<broker>/202510/ \
       --fills-dir logs/fills/202510/ \
       --export-md reports/audit/reconciliation/20251031_<broker>.md \
      --threshold-balance 0.5R --threshold-match 0.99
     ```
   - Exit codeが0以外の場合はエラーログを確認し、`logs/audit/reconciliation_<timestamp>.jsonl`を参照する。
   - チケット/注文単位の証跡を提示する際は`tradectl audit trace --order <ticket_id> --export reports/audit/order_trace/<ticket_id>.md`を実行し、Kill Switch/Reduce-Only判定と併せて監査ログへ添付する（AC-06）。
3. **差分レビューと是正判断**
   - Markdownレポート内の`Actions Required`テーブルを精査し、`variance`項目がある場合は`RUN-REC-02`の調査を起動。
   - `tradectl reconcile preview --statement <file> --broker <id>`でフォーマット異常を確認し、必要なら`statement_reconciliation.yaml`へ列マッピングを追加。
   - `tradectl governance lifecycle simulate --scenario suspension`で重大差分時の影響を評価し、Ops/Risk/POへエスカレーション。
4. **フォローアップと連携**
   - 結果を`validation_playbook/AC-64_reconciliation.md`へ追記し、Evidenceハッシュを記録。
   - 差分が残る場合は`tradectl finance ledger generate --period 2025-10 --mode live --include-pending`を実行し、`RUN-REC-02`と`RUN-TAX-01`へハンドオフする。
   - Ops Worklogに`tradectl ops log add --task reconciliation --duration <min>`で記録し、Ops Agendaへ改善タスクを追加。

## チェックリスト
- [ ] ステートメントと`statement_reconciliation.yaml`の整合を確認した
- [ ] `tradectl reconcile statements`を実行し、Markdown/JSON結果を保存した
- [ ] `match_rate`と`balance_diff`が閾値を満たしているか確認した
- [ ] 差分がある場合は`RUN-REC-02`調査を開始し、チケットを作成した
- [ ] `validation_playbook/AC-64_reconciliation.md`へ結果を記録した
- [ ] `metrics/reconciliation.jsonl`と監査ログをEvidenceとして保存した
- [ ] Ops Worklog/Agendaへ対応状況を登録した

## 証跡
- `reports/audit/reconciliation/<date>_<broker>.md`
- `logs/audit/reconciliation_<timestamp>.jsonl`
- `metrics/reconciliation.jsonl`
- `validation_playbook/AC-64_reconciliation.md`
- `ops_worklog.jsonl` (`task='reconciliation'`)
- `accounts/<broker>/<account_id>.yaml`（変更有無の差分）

## サインオフ
| 役割 | 氏名/署名 | 日時 |
| --- | --- | --- |
| Back Office Lead | | |
| Ops Manager | | |
| Risk Manager | | |
| Product Owner | | |

## 改訂履歴
| 版 | 日付 | 概要 | 編集者 |
| --- | --- | --- | --- |
| v1.0 | 2025-11-03 | 初版作成（ステートメント突合手順を定義） | Back Office Lead |
