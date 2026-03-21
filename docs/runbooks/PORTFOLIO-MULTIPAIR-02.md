---
id: PORTFOLIO-MULTIPAIR-02
title: Multi-pair Pilot Rollout And Completion Gate
owners:
  - Portfolio Integrator
review_cycle_days: 30
linked_fr:
  - FR-55
  - FR-62
docops:
  related_commands:
    - tradectl portfolio multi-pair-pilot
    - tradectl portfolio multi-pair-pilot --run
---

# PORTFOLIO-MULTIPAIR-02: Multi-pair pilot rollout と completion gate

> **Runbook版数**: v0.1  
> **最終更新日**: 2026-03-21  
> **最終更新者**: Portfolio Integrator

## 目的
- `multi_pair_preparation` で `promote_shadow_pilot` になった pair を shadow-first で pilot rollout する。
- pilot rollout を単発判断で終わらせず、stable streak を使って次の pair expansion 判断へつなぐ。

## トリガー
- `daily_shadow_ops_summary.multi_pair_pilot_completion_gate_status=ready_for_rollout`
- `next_action=start_multi_pair_pilot_rollout`

## 実行
1. latest multi-pair preparation が `promote_shadow_pilot` か確認する。
2. guardrail / suppression / recovery unresolved が無いことを確認する。
3. packet を生成する。  
   `tradectl portfolio multi-pair-pilot`
4. rollout ledger を付けて開始する。  
   `tradectl portfolio multi-pair-pilot --run`
5. daily ops summary で `multi_pair_pilot_completion_gate_status` と `stable_streak_days` を追う。

## 判定
- `ready_for_rollout`
  - pilot 開始可能
- `monitoring`
  - pilot は進行中だが、まだ stable day が足りない
- `qualified_for_pair_expansion`
  - required stable day を満たしたので、次の pair expansion 候補 review へ進める
- `blocked`
  - alert / discrepancy / recovery / suppression / guardrail のいずれかで停止

## 現行 gate
- `required_stable_days = 5`
- `alert_level != critical`
- `active_discrepancy_count = 0`
- `runtime_guardrail_status not in {blocked, manual_clear_required}`
- `rollout_suppression_status != active`
- `shadow_feedback_recovery_resolution_status in {resolved, not_required}`

## 証跡
- `logs/ops/multi_pair_pilot_rollout.jsonl`
- `reports/analysis/shadow/multi_pair_pilot_history.jsonl`
- `reports/analysis/shadow/multi_pair_pilot_rollout.json`
- `reports/analysis/shadow/multi_pair_pilot_rollout.md`
- `reports/analysis/shadow/daily_shadow_ops_summary_<stamp>.json`

## 変更履歴
| 日付 | 変更内容 | 変更者 |
| --- | --- | --- |
| 2026-03-21 | 初版作成 | Portfolio Integrator |
