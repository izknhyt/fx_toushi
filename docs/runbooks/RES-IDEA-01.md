# RES-IDEA-01: Idea Registry / Research Validation 運用

> **ACカバレッジ**: FR-55/FR-62（AC番号未割当）  
> **Runbook版数**: v0.2  
> **最終更新日**: 2026-01-17  
> **最終更新者**: Codex Liaison (Research Ops代理)

## 目的
- IdeaRegistryとResearchPipelineの運用手順を明確化し、研究ステージの進行管理を標準化する。

## 適用範囲・トリガー
- 新規Idea登録時。
- `tradectl research validate` で検証を実施するタイミング。
- Stage昇格（`draft` → `screening` → `paper` → `ready`）の承認時。

## 事前準備
- `research/ideas/<idea_id>/manifest.yaml` が用意されていること。
- Validation Suite (`config/research_validation.yaml`) が最新であること。

## 手順
1. `tradectl research idea list --json` でIdea一覧を確認。
2. `tradectl research validate --strategy <id> --window 90d --export-md reports/research/validation/<id>_90d.md` を実行。
3. `tradectl research idea checklist --id <idea_id>` で不足項目を確認。
4. 要件が満たされたら `tradectl research idea stage --id <idea_id> --to <stage> --note "<reason>"` を実行。
5. 生成されたValidationレポートを `reports/validation_log/FR-55_<date>.md` に添付する。

## チェックリスト
- [ ] Validation Suiteの実行
- [ ] Checklistの未達項目を解消
- [ ] Stage遷移ログを確認
- [ ] 検証ログを更新

## エスカレーション
- Checklist未達が2回続く場合はResearch Leadへ相談。
- `tradectl research validate` の失敗が継続する場合はDataチームへエスカレーション。

## 履歴更新手順
- Runbook更新時は版数・最終更新日・更新者を更新し、`reports/governance/runbook_changelog.md`へ記録する。
