# GOV-IDEA-01: Idea Pipeline Governance

> **ACカバレッジ**: AC-50 (FR-62 Idea Pipeline)  
> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-17  
> **最終更新者**: Codex Liaison (Research Ops代理)

## 目的
- Idea Pipelineのステージ遷移とチェックリスト審査を標準化する。
- 必須エビデンスの不足・Ops Readiness低下・Model Risk未承認を即時に可視化する。

## 適用範囲・トリガー
- `tradectl research idea stage --to <stage>` 実行時に `status=blocked` が返却された場合。
- `metrics/idea_pipeline.jsonl` で `stalled` が発生した場合。

## 事前準備
- `config/idea_pipeline.yaml` のステージ定義が最新であること。
- `docs/templates/idea_checklists/<stage>.yaml` が更新済みであること。
- `config/roles.yaml` に承認者が登録済みであること。

## 手順
1. `tradectl research idea show --id <idea_id> --json` を実行し、現在のステージとチェックリストを確認する。
2. `tradectl research idea checklist --id <idea_id> --stage <stage>` で未完了項目を洗い出す。
3. 必須エビデンスが欠損している場合は `tradectl research idea checklist-update --id <idea_id> --stage <stage> --item <item_id> --status done --evidence <path>` を実行し、証跡を登録する。
4. Ops Readiness が低い場合は `tradectl ops readiness --json` を確認し、該当Runbookへエスカレーションする。
5. Model Risk が未承認の場合は `tradectl model-risk status --strategy <id>` を確認し、承認手順を完了させる。

## チェックリスト
- [ ] Ideaのステージ/チェックリストを確認
- [ ] 必須エビデンスを登録
- [ ] Ops Readiness/Model Risk の阻害要因を解消
- [ ] ステージ遷移を再実行

## エスカレーション
- 2週以上 `blocked` が継続する場合は Ops Manager に連絡する。
- Ops Readiness `status=low` の場合は `OPS-READINESS-01` に従う。

## 履歴更新手順
- Runbook更新時はバージョン番号を+0.1し、最終更新日と更新者を最新化する。
- 変更内容を`reports/governance/runbook_changelog.md`に記録する。
