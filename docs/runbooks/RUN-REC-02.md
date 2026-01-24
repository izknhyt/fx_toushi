# RUN-REC-02: Ledger差分調査・是正手順

> **ACカバレッジ**: FR-64, FR-59, AC-53  
> **Runbook版数**: v1.1  
> **最終更新日**: 2026-01-21  
> **最終更新者**: Back Office Lead (Doc Maintainer)  
> **仕様参照**: detailed_design_fx_signal_tool_v1.md §25.1-25.3, §47.1-47.3; basic_design_fx_signal_tool_v1.md:121,288; 要件定義（テンプレ形式）v_1.md:183,188  
> **運用シナリオID**: TR-32 (Ledger variance remediation)  
> **関連メトリクス/ログ**: parquet/backoffice/ledger_<mode>_<period>.parquet, jsonl/backoffice/taxlots_<mode>_<period>.jsonl, metrics/backoffice_ledger.jsonl, logs/audit/backoffice_<date>.jsonl, reports/ops/aggregator/<date>.md, reports/audit/reconciliation/<date>_<broker>.md  
> **外部資料**: reports/tax/ledger_summary_<mode>_<period>.md, validation_playbook/AC-64_reconciliation.md, docs/runbooks/RUN-AUD-02.md, docs/runbooks/RUN-TAX-01.md

## 目的
- Ledger生成後に`reconciliation_status='variance'`や`pending`となったエントリを特定し、原因（欠損ステートメント、入力誤差、手数料/税差分）を切り分ける。
- 必要に応じて手動調整 (`AdjustmentRecord`) を記録し、監査ログと税務レポートへの影響を最小化する。
- 是正結果を`reports/tax/ledger_summary_<mode>_<period>.md`および`reports/audit/reconciliation/`へ反映し、後続の`RUN-TAX-01`や監査パックに突合可能な状態を整える。

## トリガー
- `tradectl finance ledger generate --period <period> --mode <mode>`後にCLIが`pending_entries>0`または`variance_entries>0`を通知したとき。
- `metrics/backoffice_ledger.jsonl`で`reconciliation_variance>0`が7日連続で計測されたとき。
- `RUN-AUD-02`で`Actions Required`に差分調査が残ったまま`due`を超過したとき。
- Ops Agendaの`Critical First`に`ledger_variance`が追加されたとき。

## 責務
- **Back Office Lead**: Ledger解析、調整案作成、CLI実行。
- **Ops Manager**: Evidence整理、Ops Worklog登録、関連Runbook連携。
- **Risk Manager**: 差分がリスク閾値へ与える影響評価（エクスポージャ、PnL）。
- **Compliance Advisor**: 手動調整の承認・署名、外部監査連携。

## 手順
1. **差分の抽出**
   - `tradectl finance ledger diff --period 2025-10 --mode live --export-md reports/tax/ledger_diff_2025-10.md`を実行し、差分テーブルを取得。
   - `parquet/backoffice/ledger_live_202510.parquet`を`poetry run tools/ledger_inspect.py --period 2025-10 --mode live --status variance`でフィルタし、対象`LedgerEntry`をJSONで保存。
2. **原因の切り分け**
   - ステートメント欠損: `reports/audit/reconciliation/20251031_<broker>.md`を参照し、`unmatched_statements`に該当行があるか確認。ある場合は`RUN-AUD-02`へ差戻し。
   - データ遅延/欠損: `RUN-ACC-01`のステップでアカウントスナップショットを再取得し、`AccountSnapshot`の更新時刻を確認。
   - 手数料/税差分: `config/tax/<jurisdiction>.yaml`と当該`LedgerEntry.fees/tax_category`を比較し、乖離が生じたイベントを`logs/audit/backoffice_<date>.jsonl`から抽出。
3. **調整の適用**
   - 是正が必要な場合は`docs/backoffice/adjustments/<YYYYMM>.md`へ案を記載し、承認者の電子署名を取得。
   - CLIで調整を適用:
     ```console
     tradectl finance ledger adjust \
       --period 2025-10 --mode live \
       --type tax_adjustment \
       --amount -125.40 \
       --reason "Broker swap correction" \
       --supporting reports/audit/reconciliation/20251031_<broker>.md
     ```
   - 適用後に`tradectl finance ledger generate --period 2025-10 --mode live --include-pending=false`を再実行し、差分が解消されていることを確認。
4. **連携と報告**
  - `reports/tax/ledger_summary_live_2025-10.md`を更新し、調整内容・承認者・ハッシュを記載。
   - `validation_playbook/AC-64_reconciliation.md`と`validation_playbook/FR-59_audit_bundle.md`へ調整の証跡をリンク。
   - Ops Worklogへ`tradectl ops log add --task ledger_variance --duration <min>`で記録し、Ops AgendaのCriticalタスクをクローズ。
   - 税務・監査へ影響がある場合は`RUN-TAX-01`を起動し、`audit_pack/<period>/finance/`へ最新Ledgerを再添付。

## チェックリスト
- [ ] `tradectl finance ledger diff`の結果を保存し、差分エントリを抽出した
- [ ] ステートメント/CSV/Manifestなど関連ソースを参照し、差分原因を特定した
- [ ] 必要な場合は調整案を`docs/backoffice/adjustments/`へ起票し、承認者の署名を取得した
- [ ] `tradectl finance ledger adjust`/`generate`を再実行して差分が解消されたことを確認した
- [ ] `reports/tax/ledger_summary_<mode>_<period>.md`とValidation Playbookを更新した
- [ ] Ops WorklogとOps Agendaのタスクを更新した
- [ ] `RUN-TAX-01`または`RUN-AUD-02`へのハンドオフを実施し、リンクを記録した

## 証跡
- `reports/tax/ledger_diff_<period>.md`, `reports/tax/ledger_summary_<mode>_<period>.md`
- `parquet/backoffice/ledger_<mode>_<period>.parquet`, `jsonl/backoffice/taxlots_<mode>_<period>.jsonl`
- `logs/audit/backoffice_<timestamp>.jsonl`
- `docs/backoffice/adjustments/<YYYYMM>.md`
- `validation_playbook/AC-64_reconciliation.md`, `validation_playbook/FR-59_audit_bundle.md`
- `ops_worklog.jsonl` (`task='ledger_variance'`)

## サインオフ
| 役割 | 氏名/署名 | 日時 |
| --- | --- | --- |
| Back Office Lead | | |
| Ops Manager | | |
| Risk Manager | | |
| Compliance Advisor | | |

## 改訂履歴
| 版 | 日付 | 概要 | 編集者 |
| --- | --- | --- | --- |
| v1.0 | 2025-11-03 | 初版作成（Ledger差分調査フロー定義） | Back Office Lead |
| v1.1 | 2026-01-21 | ledger_summary/taxlotsのmode別パスへ更新 | Back Office Lead |
