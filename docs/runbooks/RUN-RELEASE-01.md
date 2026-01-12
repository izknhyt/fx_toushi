# RUN-RELEASE-01: リリースゲート運用手順

> **ACカバレッジ**: AC-06, AC-40
> **Runbook版数**: v1.0
> **最終更新日**: 2026-01-07
> **最終更新者**: Product Owner (Doc Maintainer)
> **関連CLI**: `tradectl release prepare`, `tradectl release record`, `tradectl release verify`, `tradectl release tag`
> **関連ファイル**: `docs/release_checklist.md`, `reports/audit/release/<version>.md`, `reports/audit/release/<version>.json`

## 目的
- リリース前チェック項目を定型化し、証跡ファイルとともにゲート判断を一元管理する。
- `docs/release_checklist.md`に定義したタスクをCLIで進捗管理し、未完了の場合はGuardrailsにブロック通知を残す。

## トリガー
- リリース候補の確定（RC作成時）。
- 週次/隔週の運用リリースレビューでゲート確認が必要になったとき。

## 事前準備
- `docs/release_checklist.md`が最新の運用要件に合っていることを確認する。
- 各タスクの証跡（ログ/レポート/検証結果）を`reports/`配下へ用意しておく。

## 手順
1. **チェックリスト準備**
   - `tradectl release prepare --version <tag>`を実行し、`reports/audit/release/<tag>.md`と`reports/audit/release/<tag>.json`が生成されることを確認する。
2. **進捗記録**
   - 各タスクの完了時に`tradectl release record --version <tag> --task <task_id> --status pass --evidence <path>`で証跡を登録する。
   - 失敗・保留の場合は`--status fail`/`pending`を指定し、理由を`docs/release_checklist.md`の注記欄に追記する。
3. **ゲート検証**
   - `tradectl release verify --version <tag>`を実行し、`status=ok`であることを確認する。
   - `status=blocked`の場合、`metrics/guardrails.jsonl`に`release_blocked`が記録されるため、是正後に再実行する。
4. **タグ付け**
   - `tradectl release tag --version <tag>`を実行し、`reports/audit/release/<tag>.tag`が生成されることを確認する。
5. **アーカイブ**
   - 完了したチェックリストを`docs/archive/releases/<tag>.md`やリリース告知（`docs/templates/release_announcement.md`）へリンクする。

## チェックリスト
- [ ] `tradectl release prepare`の出力が作成されている
- [ ] 全タスクに証跡が紐付いている
- [ ] `tradectl release verify`が`status=ok`
- [ ] `tradectl release tag`でタグファイルを作成した

## 証跡
- `reports/audit/release/<version>.md`
- `reports/audit/release/<version>.json`
- `reports/audit/release/<version>.tag`
- `metrics/guardrails.jsonl`（ブロック通知がある場合）
