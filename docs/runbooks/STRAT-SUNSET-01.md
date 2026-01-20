# STRAT-SUNSET-01: Strategy Sunset Workflow

> **ACカバレッジ**: AC55_sunset  
> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-18  
> **最終更新者**: Codex Liaison (Ops代理)

## 目的
- 戦略のサンセット意思決定からクローズ、証跡の保存までを標準化する。

## 適用範囲・トリガー
- Strategy Boardで終了判断が出たとき。
- リスク同意またはガバナンス判断により戦略停止が必要になったとき。

## 手順
1. `tradectl governance sunset issue --strategy <id> --reason <reason> --issued-by <actor> --effective-at <UTC>` を実行。
2. `tradectl governance sunset plan --strategy <id> --export-md reports/governance/sunset/<id>/plan_<date>.md` を実行。
3. 生成された plan の action を順に `tradectl governance sunset execute --plan-id <id> --step-id <step> --executed-by <actor> --evidence <path>` で完了させる。
4. すべての step 完了後に `tradectl governance sunset complete --plan-id <id> --reallocation-status <status>` を実行。
5. 必要に応じて `tradectl portfolio reallocate suggest --plan-id <id>` を実行し、再配分案を記録する。
6. `docs/validation_playbook/AC55_sunset.yaml` にエントリが追加されたことを確認する。

## チェックリスト
- [ ] Runbook参照が plan と audit に記録されている
- [ ] Evidenceファイルが保存されている
- [ ] Validation playbook へ記録された

## エスカレーション
- 48時間以内に完了できない場合は Ops Lead にエスカレーション。

## 履歴更新手順
- Runbook更新時は版数・最終更新日・更新者を更新し、`reports/governance/runbook_changelog.md`へ記録する。
