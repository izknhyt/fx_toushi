# GOV-LIC-01: マーケットデータライセンス運用

> **ACカバレッジ**: M12_license_compliance  
> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-18  
> **最終更新者**: Ops Manager / Codex Liaison

## 目的
- 有償フィードの契約・利用制限・コスト・レビュー履歴を一元化し、監査証跡として保持する。
- `LicenseRegistryService`とCLIを通じて契約書とチェックリストを同期する。

## 手順
1. **契約登録**: `reports/governance/licensing/license_registry.yaml`に契約情報を登録する。
2. **契約書添付**: `tradectl governance licensing attach --provider <id> --contract <pdf> --compliance-id <id>`を実行し、契約書ハッシュを記録する。
3. **チェックリスト**: `tradectl governance licensing checklist --provider <id> --compliance-id <id>`でチェックリストを生成し、レビュー担当を記入する。
4. **レビュー**: `tradectl governance licensing review --provider <id> --notes <md> --compliance-id <id>`を実行し、レビュー記録を残す。
5. **評価連携**: `tradectl data feed-eval run --provider <id>`の評価結果とあわせ、コスト/制限/再配布条件を見直す。
6. **更新通知**: 期限90日前に再レビューを行い、`license_registry`の`last_review_at`を更新する。

## 関連リンク
- `docs/runbooks/RUN-DATA-07.md`
- `reports/governance/licensing/`
