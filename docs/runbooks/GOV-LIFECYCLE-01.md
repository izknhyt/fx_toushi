# GOV-LIFECYCLE-01: 戦略ライフサイクル運用

> **ACカバレッジ**: AC-55, FR-55/56/61  
> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-18  
> **最終更新者**: Ops Manager / Codex Liaison

## 目的
- Strategy Lifecycle Gate の判定、証跡、フォローアップを一元化する。
- Strategy Board / Scoreboard / Ops Readiness と連携して昇格・停止判断を透明化する。

## 手順
1. `tradectl governance lifecycle status --strategy <id>`で現状のゲート判定を確認する。
2. `tradectl governance lifecycle evaluate --strategy <id> --gate <gate_id> --json`で再評価する。
3. ブロック時は`blocked_reasons`を確認し、対応Runbookを参照する。
4. 強制解除が必要な場合は`--force`を使い、`config/roles.yaml`の`lifecycle_override`権限を確認する。
5. 評価結果は`reports/governance/lifecycle/`と`metrics/strategy_lifecycle.jsonl`に記録する。

## 関連リンク
- `docs/validation_playbook/strategy_lifecycle.yaml`
- `docs/runbooks/STRAT-PROMOTE-01.md`
