# RUN-DEGRADE-01: Acceptable Degradation Playbook

> **ACカバレッジ**: AC34_degradation  
> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-18  
> **最終更新者**: Codex Liaison (Ops代理)

## 目的
- Acceptable Degradation発生時の対応を標準化し、証跡と復旧判断を一元化する。

## 適用範囲・トリガー
- `health.status=degraded` または `tradectl ops degrade trigger` 実行時。

## 手順
1. `tradectl ops degrade trigger --scenario data_latency --severity high` を実行。
2. `tradectl ops degrade status --instance <id>` で進捗を確認。
3. `tradectl ops degrade ack --instance <id> --node <node_id> --evidence <path>` を順に実行。
4. すべてのノード完了後に `tradectl ops degrade recover --instance <id> --attach-report <path>` を実行。
5. `docs/validation_playbook/AC34_degradation.yaml` にエントリが追加されたことを確認。

## チェックリスト
- [ ] Evidenceが添付されている
- [ ] Runbook参照が記録されている
- [ ] Recoveryレポートが添付されている

## エスカレーション
- 120分超の復旧遅延はOps Readinessへ減点対象として記録。

## 履歴更新手順
- Runbook更新時は版数・最終更新日・更新者を更新し、`reports/governance/runbook_changelog.md`へ記録する。
