# RUN-TAX-01: 税務レポート生成・提出手順

> **ACカバレッジ**: FR-59, FR-64, NFR-05  
> **Runbook版数**: v1.1  
> **最終更新日**: 2026-01-07  
> **最終更新者**: Back Office Lead (Doc Maintainer)  
> **仕様参照**: detailed_design_fx_signal_tool_v1.md §47.1-47.4, §48.2-48.4; basic_design_fx_signal_tool_v1.md:278,313; 要件定義（テンプレ形式）v_1.md:183  
> **運用シナリオID**: DRILL-tax_reconciliation (Tax readiness drill)  
> **関連メトリクス/ログ**: metrics/backoffice_ledger.jsonl, metrics/secure_share.jsonl, logs/audit/backoffice_<date>.jsonl, audit_pack/<period>/finance/, reports/tax/ledger_summary_<period>.md, reports/tax/<year>/<mode>_tax_report.{md,csv}  
> **外部資料**: docs/templates/tax_report_jp.md, config/tax/<jurisdiction>.yaml, secure_share config/share_profiles/tax_accountant.yaml, validation_playbook/FR-59_audit_bundle.md, docs/runbooks/RUN-AUD-02.md, docs/runbooks/RUN-REC-02.md

## 目的
- BackOfficeLedgerとTaxLot計算を基に、税務および監査提出用の年次レポートを正確に生成し、署名付きEvidenceとして保管・共有する。
- 税務区分・為替レート・調整記録の整合を検証し、監査パック(`audit_pack/<period>/`)やSecureShareに連動する。
- 税理士/監査人への提出状況とOps証跡を追跡し、RunbookインベントリおよびValidation Data Playbookの要件を満たす。

## トリガー
- 四半期/年次決算タイミング、または税理士/監査人から提出依頼を受けたとき。
- `metrics/backoffice_ledger.jsonl`で`pending_entries=0`かつ`taxlots_generated>0`になったことを確認したとき。
- `RUN-REC-02`でLedger差分が解消された直後。
- SecureShareの`pending_share_profiles`に`tax_accountant`が登録され、提出期限が近いとOps Agendaへ通知されたとき。

## 責務
- **Back Office Lead**: Ledger/TAXレポート生成、テンプレ整備、提出記録。
- **Ops Manager**: Evidence保管、SecureShare送付手配、Ops Worklog管理。
- **Tax Advisor**: レポートレビュー、差戻し/承認、必要な補正指示。
- **Compliance Advisor**: 外部共有に関するコンプライアンス確認、署名。

## 手順
1. **前提確認**
   - `tradectl finance ledger generate --period 2025-10 --mode live --include-pending=false`を再実行し、`pending_entries=0`を確認。
   - `RUN-AUD-02`/`RUN-REC-02`のチェックリストが完了しているか確認し、必要なEvidenceリンクを`reports/tax/ledger_summary_<period>.md`に追記。
   - 為替換算設定`config/tax/jp.yaml`（例）を確認し、年平均レート/スポット基準が最新であることをレビュー。
2. **Tax Report生成**
   - CLI実行:
     ```console
     tradectl finance tax-report \
       --year 2025 --mode live \
       --template docs/templates/tax_report_jp.md \
       --export-csv \
       --jurisdiction jp \
       --out reports/tax/2025/live_tax_report.md
     ```
   - 生成されたMarkdown/CSVを確認し、`income`, `expenses`, `withholding`, `swap_income`セクションの数値がLedgerと一致していることを検証。
   - `audit.tax_report_generated`イベントが`logs/audit/backoffice_<timestamp>.jsonl`に記録されているか確認。
3. **監査パック連携**
   - `tradectl audit bundle generate --period 2025Q4`を実行し、`audit_pack/2025Q4/finance/`へLedger/Taxレポートを手動で取り込む。
   - `audit_pack/2025Q4/audit_manifest.json`に`tax_report_hash`, `ledger_hash`が追加されたことを確認。
   - Validation Data Playbook (`validation_playbook/FR-59_audit_bundle.md`)へハッシュ/署名/提出先を追記。
4. **SecureShare送付**
   - 送付パッケージを作成:
     ```console
     tradectl finance share \
       --profile tax_accountant \
       --period 2025-Q4 \
       --sources audit:2025Q4,ledger:live-2025Q4 \
       --channel sftp --dry-run
     ```
   - Dry-runで経路を確認後、実送付を実行。`metrics/secure_share.jsonl`に`status='delivered'`が記録されることを確認。
   - `ops_worklog.jsonl`へ`task='tax_report_share'`を追加し、所要時間と共有チャネルを記録。
5. **レビューとフィードバック**
   - 税理士からのフィードバックを`reports/tax/2025/review_log.md`へ記録し、差戻しがあれば`RUN-REC-02`または`RUN-AUD-02`へ再エスカレーション。
   - Ops Agendaの`Critical First`/`Validation Pending`セクションから該当タスクをクローズ。
   - `reports/governance/runbook_inventory_status.json`で本Runbookの`last_review_at`を更新し、`status=ready`に戻ることを確認。

## チェックリスト
- [ ] Ledger差分/ステートメント突合が完了している (`RUN-REC-02`/`RUN-AUD-02`リンク済み)
- [ ] `tradectl finance tax-report`のMarkdown/CSV出力を確認し、Ledger値と一致している
- [ ] `audit bundle`へLedger/Taxレポートを再添付し、ハッシュ整合を確認した
- [ ] SecureShare (`tradectl finance share`) のDry-runと本送付を完了し、`metrics/secure_share.jsonl`で`status='delivered'`を確認した
- [ ] Validation Data Playbook (`FR-59`, `AC-64`) を更新し、Evidenceハッシュと署名を追記した
- [ ] Ops Worklogと`reports/tax/2025/review_log.md`に提出記録を残した
- [ ] 税理士/Complianceからのサインを取得し、`reports/tax/<year>/<mode>_tax_report.md`へ記録した

## 証跡
- `reports/tax/<year>/<mode>_tax_report.{md,csv}`
- `reports/tax/ledger_summary_<period>.md`
- `audit_pack/<period>/finance/`, `audit_pack/<period>/audit_manifest.json`
- `metrics/backoffice_ledger.jsonl`, `metrics/secure_share.jsonl`
- `logs/audit/backoffice_<timestamp>.jsonl`, `logs/audit/secure_share_<timestamp>.jsonl`
- `reports/tax/<year>/review_log.md`
- `ops_worklog.jsonl` (`task='tax_report_share'`)

## サインオフ
| 役割 | 氏名/署名 | 日時 |
| --- | --- | --- |
| Back Office Lead | | |
| Ops Manager | | |
| Tax Advisor | | |
| Compliance Advisor | | |

## 改訂履歴
| 版 | 日付 | 概要 | 編集者 |
| --- | --- | --- | --- |
| v1.0 | 2025-11-03 | 初版作成（Taxレポート生成・共有フロー定義） | Back Office Lead |
