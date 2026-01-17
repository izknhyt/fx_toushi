# RES-SCORE-01: Strategy Score Watchlist 대응

> **ACカバレッジ**: FR-61（AC番号未割当）  
> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-17  
> **最終更新者**: Codex Liaison (Research Ops代理)

## 目的
- `alpha_score`/`decay_score` の低下を検知し、Strategy Board で再検証を促す。

## 適用範囲・トリガー
- `metrics/strategy_scores.jsonl` で `alpha_score<75` または `decay_score>35` を検知した場合。
- `tradectl board` の Strategy Snapshot に `score_watchlist_flags` が付与された場合。

## 事前準備
- `reports/research/metrics/` に評価対象の指標が揃っていること。
- `config/strategy_manifest.yaml` が最新であること。

## 手順
1. `tradectl strategy score update --window 24w` を実行してスコアを更新。
2. `tradectl strategy score report --week <YYYY-Www>` で週次レポートを生成。
3. `reports/research/alpha_score/<YYYY-Www>.md` を Strategy Board に共有。
4. Watchlist 戦略は再検証タスクを起票し、`reports/governance/strategy_board/` へ記録。

## チェックリスト
- [ ] Score metrics が更新されている
- [ ] スコアレポートが出力されている
- [ ] Watchlist 戦略の再検証タスクが登録されている

## エスカレーション
- `decay_score>35` が2週継続した場合は Ops Manager へ報告。
- `alpha_score<75` が改善しない場合は Strategy Board で再検証決議。

## 履歴更新手順
- Runbook更新時は版数・最終更新日・更新者を更新し、`reports/governance/runbook_changelog.md`へ記録する。
