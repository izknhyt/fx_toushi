# Codex Issue テンプレート

Codex向け実装依頼時に利用するIssueテンプレート。§0.6.9の前提チェックと§0.6.11の必須添付物を網羅し、Opsレビューでの監査導線を確保する。

## 1. 基本情報
- Issue ID: OPS-XX
- タイトル:
- 概要 / 目的:
- 対象Packet / PR:
- 想定Milestone:
- 担当 (Ops / Dev / Codex):
- 関連Runbook / Validation Data Playbook:
- 依存する設計セクション: §

## 2. 前提チェック (CHK-0.6.9)
- [ ] CHK-0.6.9-1: `poetry install --no-root` & `python -m tradectl --help` 証跡 (`logs/ops/`)
- [ ] CHK-0.6.9-2: `pytest -k smoke` CI整合 (`reports/validation_log/`)
- [ ] CHK-0.6.9-3: レビュー記録 & Prompt Packet 整備 (`docs/review_log.md`, `docs/prompt_packages/`)
- [ ] CHK-0.6.9-4: リスク閾値スキーマ整合 (`reports/validation_log/` or CI Job ID)
- [ ] CHK-0.6.9-5: Issue/PRへ§0.6.8番号引用 (`logs/ops/`メモ or PRリンク)
- [ ] CHK-0.6.9-6: CLIスナップショット / Runbook同期 (`docs/runbooks/`, `snapshots/`)
- [ ] CHK-0.6.9-7: Configテンプレ差分なし (`git diff config/`レビュー)
- [ ] CHK-0.6.9-8: 監査ログ導線確認 (`reports/validation_log/`, `logs/ops/audit/`)
- [ ] CHK-0.6.9-9: Strategy Plugin契約タスク連携（該当時）

## 3. 必須添付物 (§0.6.11)
- [ ] `pytest -k config_schema_smoke` 実行ログ（`reports/validation_log/`配下に保存）
- [ ] `poetry run schema-validate ...` コマンド結果（対象スキーマ名とともに`reports/validation_log/`へ格納）
- [ ] CLIスナップショット (`tradectl benchmark replay` / `tradectl status` 等) の出力またはキャプチャ（`logs/ops/`または`snapshots/`）
- [ ] Runbookリンク & Validation Data Playbook ID（例: `RUN-FEATURE-FLAG-01 §5.1`, `VDP-AC45-20250312`）
- [ ] その他必須証跡（`docs/implementation_packets/`, `reports/`）: 

## 4. 作業内容 / 期待結果
- 実装・設定変更詳細:
- テスト観点と期待結果:
- Rollback / フォールバック手順:

## 5. 変更理由とOps確認事項
- 変更理由 (Why now?):
- Opsレビュー時の確認ポイント:
  - 証跡保存先は`reports/validation_log/`・`logs/ops/`と整合しているか
  - Runbook / Validation Data Playbookが最新か
  - Codex PR本文に必須添付物が反映されるか

## 6. フォローアップ / リスク
- 追加フォローアップの有無:
- 残リスクと対応計画:

---

<!-- 記入例:
Issue ID: OPS-58
概要: Codex Issueテンプレへ§0.6.11必須添付物を反映し、監査ログの保存先を標準化する。
チェックリスト:
- [x] CHK-0.6.9-1: `logs/ops/20250312_env_setup.log`
- [x] CHK-0.6.9-2: CI Job #4521 (`reports/validation_log/20250312_pytest_smoke.md`)
- [x] CHK-0.6.9-4: `reports/validation_log/20250312_schema_validate_bundle.md`
- [x] `pytest -k config_schema_smoke` ログ添付済 (`reports/validation_log/20250312_config_schema_smoke.log`)
- [x] CLIスナップショット: `logs/ops/tradectl_benchmark_replay_20250312.txt`
- [x] Runbookリンク: `RUN-FEATURE-FLAG-01 §5.1`, Validation Data Playbook: `VDP-AC45-20250312`
添付ファイル保存先: `reports/validation_log/20250312_config_logs/`, `logs/ops/OPS-58/`
変更理由: 監査所見(#9)対応。Opsレビューで証跡リンクを即参照できるようにする。
Ops確認事項: (1) 保存先ディレクトリ作成済、(2) Runbook参照更新不要、(3) Codex PRテンプレ差分反映済み。
-->
