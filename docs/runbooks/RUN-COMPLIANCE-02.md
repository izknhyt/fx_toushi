# RUN-COMPLIANCE-02: Compliance Regression (Stop/Freeze & Capital Guard)

> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-18  
> **最終更新者**: Compliance Lead (Doc Maintainer)

> **参照**: [詳細設計 §61 Compliance Regression](../../detailed_design_fx_signal_tool_v1.md#61-stopfreeze検証--キャピタルガード回帰ハーネス設計ac-31ac-41-fr-50fr-51連携-m2準備)
> **関連コマンド**: `tradectl compliance regression generate`, `tradectl compliance regression run`, `tradectl compliance regression diff`

## 目的
- Stop/Freeze距離・丸め・キャピタルガードの回帰試験を定期実施し、AC-31/AC-41の逸脱を検知する。

## トリガー
- ブローカー仕様更新、`config/broker_rules.yaml`変更、またはRisk/Complianceレビュー時。

## 手順
1. **シナリオ生成**
   - `tradectl compliance regression generate --per-pair 50 --profile paper --out tmp/scenarios/<run_id>`
2. **回帰実行**
   - `tradectl compliance regression run --profile paper --scenarios tmp/scenarios/<run_id> --capitalsim baseline`
   - `--capitalsim stress`でAC-41シナリオを再実行
3. **差分レビュー**
   - `tradectl compliance regression diff --current reports/compliance/regression/<date>.json --against reports/compliance/regression/<prev_date>.json`
4. **Validation Playbook更新**
   - `docs/validation_playbook/AC31_stop_freeze.yaml`
   - `docs/validation_playbook/AC41_capital_guard.yaml`
5. **Ops Agenda/Worklog**
   - 逸脱がある場合、`OpsAgenda`へFollow-upを登録。
   - `tradectl ops log add --task compliance_regression --owner compliance`で記録。

## 証跡
- `reports/compliance/regression/`
- `metrics/compliance_regression.json`
- `logs/audit/compliance_regression.jsonl`
