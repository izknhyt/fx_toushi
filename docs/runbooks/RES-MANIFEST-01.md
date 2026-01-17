# RES-MANIFEST-01: Strategy Manifest Renewal

> **ACカバレッジ**: FR-56（AC番号未割当）  
> **Runbook版数**: v0.2  
> **最終更新日**: 2026-01-17  
> **最終更新者**: Codex Liaison (Research Ops代理)

## 目的
- `strategy_manifest.yaml` の有効期限/依存データ整合性を検証し、期限切れ前に再検証を実施する。

## 適用範囲・トリガー
- `tradectl strategy manifest validate` で `deprecated`/`blocked` が出た場合。
- 期限切れ14日前通知（ManifestHealthJob）が Ops Worklog にTODOを登録した場合。

## 事前準備
- `config/strategy_manifest.yaml` の最新版が存在すること。
- `reports/research/manifest_drafts/` に該当戦略の ResearchManifest が存在すること。
- Validation Playbook (`docs/validation_playbook/`) と Data Manifest (`reports/data_manifest.json`) を最新化済みであること。

## 手順
1. `tradectl strategy manifest validate --json` で該当戦略の期限/依存エラーを確認。
2. ResearchManifest (`reports/research/manifest_drafts/`) を更新し、Data Manifest 参照と一致させる。
3. 必要な Validation Playbook と Data Manifest を更新し、再検証メモを作成。
4. `tradectl strategy manifest renew --id <strategy> --force-status active --note "renewed"` を実行。
5. 変更を `reports/governance/strategy_board/` に記録し、Runbook更新履歴へ追加。

## チェックリスト
- [ ] Validation Playbook が存在する
- [ ] Data Manifest が最新である
- [ ] Manifest の `last_validated_at` が更新されている
- [ ] Ops Worklog に対応ログが残っている

## エスカレーション
- `blocked` が解消しない場合は Research Lead と Ops Manager に共有。
- `missing_data_manifest` が継続する場合は Dataチームへエスカレーション。

## 履歴更新手順
- Runbook更新時は版数・最終更新日・更新者を更新し、`reports/governance/runbook_changelog.md`へ記録する。
