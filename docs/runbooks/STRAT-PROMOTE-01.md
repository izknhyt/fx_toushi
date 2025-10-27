---
id: STRAT-PROMOTE-01
title: Strategy Promotion Gate Operations
owners:
  - Research Lead (Doc Maintainer)
  - Risk Manager (Co-reviewer)
review_cycle_days: 30
linked_fr:
  - FR-55
  - FR-62
linked_ac:
  - AC-46
linked_nfr:
  - NFR-21
docops:
  agenda_tags:
    - research.promotion
  validation_playbook_ids:
    - AC46_promotion_gate
  related_commands:
    - tradectl research promote
    - tradectl research checklist show
    - tradectl research checklist approve
    - tradectl research promote simulate
---

# STRAT-PROMOTE-01: 研究昇格ゲート運用手順

> **Runbook版数**: v0.1  
> **最終更新日**: 2025-03-10  
> **最終更新者**: Research Lead (Doc Maintainer)

## 目的
- `PromotionChecklistService`が収集した昇格要件を確認し、`tradectl research promote`実行時の自動ブロック条件を満たす。 (`src/interfaces/cli/research_promote.py`参照)
- Paper/LABステージからの昇格で必要なEvidence、Validation、リスク承認を整備し、AC-46/NFR-21のコンプライアンス基準を満たす。
- Ops/Research/Riskの各チームが承認責務・証跡保管先・再申請フローを共有し、Promotion履歴を追跡できる状態を維持する。

## 適用範囲・トリガー
- `tradectl research promote --strategy <id> --to paper|ready|live_candidate` を開始する際。
- `promotion.blocked`イベントが発火した場合の再申請準備。
- 30日ごとのDocOpsレビューサイクルまたは戦略Boardで昇格議題が上がった際。

## 役割と承認フロー
| 役割 | 主な責務 | 承認・サイン箇所 |
| --- | --- | --- |
| Research Lead | 昇格申請の起票、Evidence準備、実験結果の説明 | `reports/research/promotion/<strategy_id>_<YYYYMMDD>.md` |
| Quant Lead | 実験・バックテストの妥当性レビュー、シミュレーション確認 | `tradectl research promote --dry-run`出力へのコメント |
| Risk Manager | リスク承諾状態、Validation、Ops readinessの確認 | `validation_playbook/AC46_promotion_gate.yaml`サイン欄 |
| Ops Manager | Ops Agendaタスク・Runbook準備の確認、運用影響評価 | `OpsAgenda`アイテムの承認欄 |
| Product Owner | 最終承認およびライフサイクル更新指示 | `Strategy Board`議事録・Decision Journal |

## 事前準備
- `tradectl research checklist show --strategy <id> --to paper --json`で最新チェックリストを取得し、`status='fail'`項目を洗い出す。
- `validation_playbook/AC46_promotion_gate.yaml`に前回レビューの証跡が格納されていることを確認し、未提出項目をOps AgendaでTODO化。
- `RiskDisclosureEnforcer`の`consent_reference_id`が有効 (`tradectl compliance status --user <id>` など) であることを確認。
- `config/strategy_manifest.yaml`が`docs/schemas/strategy_manifest.schema.json`および`pytest -k config_schema_smoke`で検証済みか確認し、差分レビュー時にテストログを添付する。
- `ExperimentTrackerService`最新実行 (`reports/research/<strategy_id>/experiments/<run_id>.json`) を揃え、必要なノートブック/レポートを保存。

## 手順

### 1. チェックリストギャップの把握
1. `tradectl research checklist show --strategy <id> --to paper --missing-only --include-evidence`を実行し、未充足項目と必要Evidenceリンクを抽出する。
2. 出力を`reports/research/promotion/<strategy_id>_<YYYYMMDD>_checklist.md`に保存し、各項目に担当者・期日を追記する。
3. `risk_consent_valid`や`ops_readiness_score`などの自動項目は最新データを確認し、欠損があれば関係チームへ連絡する。

### 2. Evidence整備とValidation更新
1. `ExperimentTrackerService`から取得した`experiment_runs`をレビューし、PF/Sharpe/MaxDD指標が目標値（例: `pf_oos>=1.05`, `max_dd<=0.12`）を満たすか確認。
2. 主要Evidence（ノートブックPDF、メトリクスJSON、リスク評価メモ）を`reports/research/promotion/<strategy_id>/<YYYYMMDD>/`に配置。
3. `validation_playbook/AC46_promotion_gate.yaml`にRun ID、Evidenceパス、レビュー日、サインを追記。Ops ManagerとRisk Managerが連名で承認する。

### 3. ドライランと差分確認
1. `tradectl research promote --strategy <id> --to paper --dry-run --note "<summary>"`を実行し、`PromotionResult`が`status='pass'`になるか確認。
2. ブロックされた場合は`reasons`と`auto_fix_hint`をOps Agendaへ転記し、担当者と期限を設定。必要に応じて`tradectl research checklist approve --strategy <id> --item <item_id> --note <text> --attach <path>`でマニュアル承認を記録。
3. Dry-run結果を`reports/research/promotion/<strategy_id>_<YYYYMMDD>_dryrun.json`として保存し、Quant LeadとRisk Managerにレビュー依頼を送る。

### 4. 最終承認ミーティング
1. Research LeadがDry-run結果とEvidenceをまとめ、Strategy Boardまたは昇格レビュー会議で提示。
2. Product Ownerが昇格可否を決定し、`DecisionJournalManager`へ`decision='promotion_<strategy_id>_<stage>'`を記録。関連RunbookとValidation IDを明記する。
3. 承認済みの場合、Ops Managerが`RUN-HITL-01`や`RUN-RISK-01`など関連Runbookの準備ステップが完了しているか確認。

### 5. 昇格実行と事後手続き
1. `tradectl research promote --strategy <id> --to paper --attach reports/research/promotion/<strategy_id>/<YYYYMMDD>/evidence.zip --note "Approved by <names>"`を実行する。
2. 実行ログを`reports/research/promotion/<strategy_id>_<YYYYMMDD>.md`に貼り付け、関係者のサインを取得。
3. `validation_playbook/AC46_promotion_gate.yaml`へ`PromotionReceipt`情報（`status`, `timestamp`, `lifecycle_event_id`）を追記し、Evidenceのハッシュを登録。
4. `tradectl research promote review --strategy <id> --recent 3`（実装予定）または`StrategyLifecycleOrchestrator`のログでステージ更新を確認し、Ops Agendaのタスクを完了させる。

## 証跡と保存先
- チェックリスト出力: `reports/research/promotion/<strategy_id>_<YYYYMMDD>_checklist.md`
- Evidence一式: `reports/research/promotion/<strategy_id>/<YYYYMMDD>/`
- Dry-runログ: `reports/research/promotion/<strategy_id>_<YYYYMMDD>_dryrun.json`
- 昇格実行レポート: `reports/research/promotion/<strategy_id>_<YYYYMMDD>.md`
- Validation: `validation_playbook/AC46_promotion_gate.yaml`
- Decision記録: `decision_records/promotion/<strategy_id>_<YYYYMMDD>.md`

## チェックリスト
- [ ] `tradectl research checklist show`の未充足項目が解消されている
- [ ] Evidenceディレクトリが最新実験結果・リスク評価を含み、ハッシュがValidation Playbookへ登録されている
- [ ] `tradectl research promote --dry-run`で`status='pass'`を確認し、差分ログを保存している
- [ ] Strategy Board/Decision Journalで最終承認が記録されている
- [ ] 本番昇格コマンド実行後に`PromotionReceipt`をValidation Playbookへ記録し、Ops Agendaタスクを完了に設定している

## エスカレーション
- Dry-runが`status='blocked'`のまま14日以上経過した場合、Product Ownerへ報告し、`OpsAgenda`に`severity=high`で`promotion.followup`タスクを追加。
- リスク承諾 (`risk_consent_valid`) が無効な場合は`COMPLIANCE-01`を参照し、再承諾フローを完了するまで昇格を停止。
- `OpsReadinessEvaluator`スコアが80未満の場合はOps Managerへ是正策を依頼し、必要に応じて昇格審査を延期する。

## 変更履歴
| 日付 | 変更内容 | 変更者 |
| --- | --- | --- |
| 2025-03-10 | 初版作成（Promotion Gate CLIとValidation連携を整理） | Research Lead |
