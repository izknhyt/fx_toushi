---
id: COACHING-01
title: Trader Workflow Coaching Loop
owners:
  - Ops Manager (Doc Maintainer)
  - Product Coach (Workflow Coach)
review_cycle_days: 7
linked_fr:
  - FR-44
  - FR-48
linked_ac:
  - AC-10
linked_nfr:
  - NFR-11
  - NFR-28
docops:
  agenda_tags:
    - ops.coaching
  validation_playbook_ids:
    - AC10_human_performance
  related_commands:
    - tradectl ops coaching summary
    - tradectl ops coaching insight create
    - tradectl ops coaching review
    - tradectl ops coaching simulate
---

# COACHING-01: トレーダーワークフロー・コーチングレビュープレイブック

> **Runbook版数**: v0.1  
> **最終更新日**: 2025-03-10  
> **最終更新者**: Ops Manager (Doc Maintainer)

## 目的
- `TraderWorkflowTelemetryService`が収集するイベントを分析し、ボトルネックを特定・優先度付けする。 (`src/ops/coaching.py`参照)
- `CoachingPlaybook`のスケジュール・Runbook提案・効果測定フローを週次で回し、Opsチームとトレーダーの改善サイクルを維持する。
- AC-10/NFR-11/NFR-28の指標（承認レイテンシ、チェックリスト遵守、UX応答性）を証跡化し、Validation Data Playbookに反映する。

## 適用範囲・トリガー
- 週次Opsコーチング会議（原則 水曜 15:00 JST）。
- `tradectl ops coaching insight create`で`status=over_threshold`が検知された際の臨時セッション。
- `AutomationEffectTracker`の最新測定で改善率が目標（≥10%）を下回った場合のフォローアップ。

## 役割と承認フロー
| 役割 | 主な責務 | 承認・サイン箇所 |
| --- | --- | --- |
| Ops Manager | CLI実行、Ops Agendaタスク管理、Runbook更新提案作成 | `reports/ops/coaching/<YYYYWW>.md`のサイン欄 |
| Product Coach | トレーニング内容確認、セッション設計、改善施策の優先度判定 | `tradectl ops coaching review --week <id>`出力への承認コメント |
| Product Owner | 重大改善（Impact>20%）の承認、開発チケット優先度決定 | Ops Agendaアイテムの`approved_by`欄 |
| Trader代表 | 改善施策への合意、チェックリスト追従状況のフィードバック | `validation_playbook/AC10_human_performance.yaml`のレビューワ欄 |

## 事前準備
- `metrics/trader_workflow.jsonl`が前週まで更新されているか確認し、欠損があればTelemetryチームに連絡。
- `config/coaching_thresholds.yaml`を最新コミットと照合し、閾値更新があれば変更理由をチームへ共有。
- `tradectl ops agenda list --tag coaching --pending`で未完了タスクを抽出し、ステータスを最新化。
- `validation_playbook/AC10_human_performance.yaml`の前回更新日が2週間以内であることを確認し、過去証跡との整合を取る。

## 手順

### 1. テレメトリ健全性とKPIの確認
1. `tradectl ops coaching summary --window 14d --export-md reports/ops/coaching/<YYYYWW>_summary.md`を実行し、`avg_approval_latency`, `guarded_time_ratio`, `checklist_completion_rate`, `mistake_rate`を確認する。
2. `--json`オプションで取得した出力を`metrics/coaching_insights.jsonl`と突合し、計測抜けや異常値がないか検証する。
3. KPIが閾値を超えた場合は`Ops Agenda`に既存タスクがあるか確認し、重複を避けるためタスクIDをメモ。

### 2. インサイト生成と優先度付け
1. `tradectl ops coaching insight create --window 7d --threshold-config config/coaching_thresholds.yaml --export-md reports/ops/coaching/<YYYYWW>_insights.md`を実行する。
2. `--dry-run`で結果が期待通りか検証し、問題なければ本実行。出力に含まれる`priority_score`、`recommended_action`、`runbook_refs`を表にまとめる。
3. `CoachingPlaybook.analyze()`が生成した`priority_score>=0.7`の項目は必ずレビュー会議に付議する。閾値未満でも重要なケースがあれば`--tag <id>`で明示する。

### 3. セッション割当とOps Agenda同期
1. `tradectl ops coaching insight create`実行時に追加された`OpsAgenda`タスクを`tradectl ops agenda list --tag coaching --window 14d --include-evidence`で確認する。
2. タスクに`due_date=<次週水曜>`が設定されているかを確認し、必要に応じて`tradectl ops agenda update --id <task_id> --due <date>`で修正する。
3. Product Coachと調整し、担当トレーナー/対象トレーダー/想定成果をOps Agendaの`notes`欄に追記する。

### 4. Runbook・トレーニング資料の改訂提案
1. `CoachingPlaybook.update_runbook()`が示す`runbook_refs`（例: `docs/runbooks/RUN-HITL-01.md`）を確認し、該当セクションをレビューする。
2. 変更案が必要な場合は`git checkout -b coaching-runbook-update`でブランチを作成し、Runbook差分を作成。`tradectl docs lint --category runbook`でLintを通す。
3. Pull Request作成後、`DocOps`レビューを依頼。マージ後は本Runbookの「変更履歴」を更新し、`OpsAgenda`の該当タスクを`completed`に変更する。

### 5. 効果測定とフォローアップ
1. 前回サイクルの効果測定として`tradectl ops coaching review --week <YYYY-WW> --diff`を実行し、`AutomationEffectTracker`が記録した改善値（%）を確認する。
2. 改善率が目標を下回った場合は`tradectl ops coaching simulate --scenario <id>`を使用して代替施策を検討し、必要に応じて新たなOps Agendaタスクを生成。
3. 実施結果と意思決定を`reports/ops/coaching/<YYYYWW>.md`へ追記し、Ops ManagerとProduct Coachがサインする。
4. 記録済みの証跡を`OpsEvidenceStore.register(category='coaching', source='reports/ops/coaching/<YYYYWW>.md')`で登録し、Validation Playbookにハッシュを添付する。

## 証跡と保存先
- 週次サマリ: `reports/ops/coaching/<YYYYWW>_summary.md`（CLI出力をエクスポート）
- インサイト一覧: `reports/ops/coaching/<YYYYWW>_insights.md`
- 効果測定ノート: `reports/ops/coaching/<YYYYWW>.md`（サイン含む）
- Validation: `validation_playbook/AC10_human_performance.yaml`（RunbookID, CLIログ, サインオフを追記）
- Automationログ: `metrics/coaching_insights.jsonl`と`metrics/trader_workflow.jsonl`

## チェックリスト
- [ ] `tradectl ops coaching summary`の最新結果を確認し、KPIが閾値内または是正タスクが登録されている
- [ ] `tradectl ops coaching insight create`の出力を保存し、優先度上位のインサイトを会議に付議
- [ ] Ops Agenda上のコーチングタスクに担当者・期限・Runbook参照が記録されている
- [ ] Runbook/トレーニング資料の改訂案が必要な場合、Pull RequestとDocOpsレビューが完了している
- [ ] `tradectl ops coaching review`で効果測定を実施し、結果を`validation_playbook/AC10_human_performance.yaml`へ記録

## エスカレーション
- `avg_approval_latency>60s`が2週連続で発生した場合はProduct Ownerへ即時報告し、`OpsAgenda`に`severity=critical`のタスクを追加。
- `checklist_completion_rate<0.9`または`mistake_rate>0.08`が検出された場合は`RUN-HITL-01`の緊急手順を参照し、再教育セッションを臨時開催。
- Telemetry欠損が24時間以上続く場合は`IncidentPostmortemService`（§63）にインシデントを起票し、`reports/audit/ops/<date>.md`へ記録。

## 変更履歴
| 日付 | 変更内容 | 変更者 |
| --- | --- | --- |
| 2025-03-10 | 初版作成（DocOpsフロントマター適用、Telemetry連携手順定義） | Ops Manager |
