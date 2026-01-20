# RUN-GOV-02: SecureShare配布手順

> **ACカバレッジ**: FR-59, FR-62, FR-64, NFR-05  
> **Runbook版数**: v1.0  
> **最終更新日**: 2026-01-17  
> **最終更新者**: Governance Lead  
> **仕様参照**: detailed_design_fx_signal_tool_v1.md §48.1-§48.4  

## 目的
- 外部共有用の証跡パッケージをSecureShareで作成・暗号化・配布する。
- 共有履歴を`docs/governance/share_register.md`で管理し、監査性を維持する。

## 手順
1. **共有対象の確認**
   - `config/share_profiles/<profile>.yaml`を確認し、許可パスと宛先を確認。
2. **パッケージ作成**
   - CLI実行例:
     ```console
     python3 tools/publish_evidence_bundle.py \
       --profile tax_accountant \
       --period 2025-Q4 \
       --sources audit:2025Q4,ledger:live_2025Q4
     ```
3. **配布確認**
   - `logs/audit/secure_share.jsonl`に`audit.evidence_shared`が記録されたことを確認。
   - `metrics/secure_share.jsonl`に`status=delivered`が記録されたことを確認。
4. **共有履歴**
   - `docs/governance/share_register.md`に配布履歴が追記されていることを確認。

## 証跡
- `reports/secure_share/<profile>/<period>/manifest.json`
- `logs/audit/secure_share.jsonl`
- `metrics/secure_share.jsonl`
- `docs/governance/share_register.md`

## 改訂履歴
| 版 | 日付 | 概要 | 編集者 |
| --- | --- | --- | --- |
| v1.0 | 2026-01-17 | 初版作成 | Governance Lead |
