# OPS-READINESS-01: オペレーションレディネス評価手順

## 目的
- `ops_readiness_score`を維持し、リリースや戦略昇格の前提となる運用体制・バックアップ整合性・演習完遂率を定量的に確認する。
- スコア低下時に是正アクションを明確化し、Kill Switch解除条件を整える。

## トリガー
- 週次レビューで`tradectl ops readiness`を実行するタイミング。
- スコアが75未満となり`HealthState=soft_stop(reason=ops_readiness_low)`へ遷移したとき。
- 新規リリース/戦略昇格/DR演習実施前の事前チェック。

## 手順
1. `tradectl ops readiness --explain`を実行し、`reports/governance/ops_readiness_<YYYYWW>.md`と照合する。スコア構成（バックアップ整合・Runbook更新率・演習完遂率・緊急プロトコル検証）を確認する。
2. 直近のバックアップ/リストア結果を`reports/drill/`および`dist/offline_bundle/`で検証し、欠損がある場合は復元テストを再実施する。
3. Runbook更新率チェックでは`docs/runbooks/`の更新履歴を確認し、未レビューの手順があれば担当者を割り当てる。
4. 緊急演習の結果を`reports/drill/emergency/<scenario>.md`と突合し、未完了のアクションアイテムをIssue化する。
5. 是正が完了したらスコアを再計算し、`tradectl ops readiness`の結果をスクリーンショットまたはログとして`reports/governance/ops_readiness_<YYYYWW>.md`へ添付する。Kill Switch解除時は承認者コメントを残す。

## 責任者
- オペレーションズマネージャ（評価実施と是正タスク調整）
- プロダクトオーナー（スコア承認とKill Switch解除判断）
- バックアップ/インフラ担当（証跡整合と演習実施）
