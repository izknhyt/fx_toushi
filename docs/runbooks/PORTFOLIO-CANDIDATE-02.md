---
id: PORTFOLIO-CANDIDATE-02
title: Baseline Candidate Onboarding And Promotion
owners:
  - Portfolio Integrator
review_cycle_days: 30
linked_fr:
  - FR-55
  - FR-62
docops:
  related_commands:
    - tradectl portfolio candidate-onboard
    - tradectl portfolio evaluate
    - tradectl portfolio review
---

# PORTFOLIO-CANDIDATE-02: Baseline candidate onboarding and safe promotion

> **Runbook版数**: v0.1  
> **最終更新日**: 2026-03-21  
> **最終更新者**: Portfolio Integrator

## 目的
- 固定した USDJPY baseline に対して、新しい candidate を `standalone -> marginal contribution -> promotion gate` の順で評価する。
- suppression / recovery / runtime guardrail drift が未解消の間は baseline promotion を止める。

## 実行条件
1. baseline portfolio が active である。
2. 最新の `daily_shadow_ops_summary` が存在する。
3. candidate strategy ids と対象 merged parquet が決まっている。

## 実行
1. candidate onboarding packet を生成する。  
   `tradectl portfolio candidate-onboard --candidate-strategies <candidate_ids> --data-path <merged_parquet> --shadow-ops-json <daily_shadow_ops_summary.json>`
2. 必要なら評価を実行する。  
   `tradectl portfolio candidate-onboard --candidate-strategies <candidate_ids> --data-path <merged_parquet> --shadow-ops-json <daily_shadow_ops_summary.json> --run`
3. packet の `decision_status` と `promotion_gate_status` を確認する。
4. `decision_status=promote` かつ `promotion_gate_status=eligible` の場合だけ promotion を実行する。  
   `tradectl portfolio candidate-onboard --candidate-strategies <candidate_ids> --data-path <merged_parquet> --shadow-ops-json <daily_shadow_ops_summary.json> --run --promote`

## 判定
- `promote`
  standalone/marginal contribution を通過し、promotion gate も `eligible`
- `research-only`
  mixed result、または promotion gate が `review_required`
- `reject`
  baseline を一貫して悪化させる
- `blocked`
  suppression / recovery / runtime guardrail により promotion 不可

## 証跡
- `reports/analysis/shadow/candidate_onboarding/*.json`
- `reports/analysis/shadow/candidate_onboarding/*.md`
- `logs/ops/candidate_onboarding_promotion.jsonl`
- promoted manifest copy

## Clear 条件
- `rollout_suppression_active = false`
- `shadow_feedback_recovery_resolution_status in {resolved, not_required, resolved_pending_clear}`
- `runtime_guardrail_status not in {blocked, guarded}`
- `safe_promotion_status = ready`

## 変更履歴
| 日付 | 変更内容 | 変更者 |
| --- | --- | --- |
| 2026-03-21 | 初版作成 | Portfolio Integrator |
