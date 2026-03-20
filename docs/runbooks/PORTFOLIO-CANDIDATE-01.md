---
id: PORTFOLIO-CANDIDATE-01
title: Portfolio Candidate Onboarding from Shadow Gate
owners:
  - Portfolio Integrator
review_cycle_days: 30
linked_fr:
  - FR-55
  - FR-62
docops:
  related_commands:
    - tradectl portfolio next-stage --phase candidate_onboarding
    - tradectl portfolio evaluate
    - tradectl portfolio review
---

# PORTFOLIO-CANDIDATE-01: Shadow soak後のcandidate onboarding実行

> **Runbook版数**: v0.1  
> **最終更新日**: 2026-03-19  
> **最終更新者**: Portfolio Integrator

## 目的
- M7/M8 の shadow soak gate が `candidate_onboarding` を返したときに、固定 baseline に対する candidate 評価を同じ導線で実行する。
- `standalone -> marginal contribution -> review` を packet 化して、手動/自動どちらでも再現可能にする。

## トリガー
- `daily_shadow_review_summary.soak_summary.ready_for_transition=true`
- `qualified_next_phase=candidate_onboarding`

## 事前準備
1. `reports/analysis/shadow/` の最新 daily review で next-stage template を確認する。
2. 比較したい `candidate_strategy_ids` を決める。
3. 対象 merged parquet を用意する。

## 実行
1. packet を生成する。  
   `tradectl portfolio next-stage --phase candidate_onboarding --candidate-strategies <candidate_ids> --data-path <merged_parquet>`
2. 実行する。  
   `tradectl portfolio next-stage --phase candidate_onboarding --candidate-strategies <candidate_ids> --data-path <merged_parquet> --run`
3. 生成された packet / evaluation / review artifact を確認する。

## 証跡
- `reports/analysis/shadow/shadow_candidate_onboarding_<stamp>.json`
- `reports/analysis/shadow/shadow_candidate_onboarding_<stamp>.md`
- `reports/analysis/shadow/shadow_candidate_onboarding_evaluation_<stamp>.json`
- `reports/analysis/shadow/shadow_candidate_onboarding_review_<stamp>.json`

## 判定
- standalone が極端に弱い候補は昇格しない。
- marginal contribution が baseline を悪化させる候補は research-only か reject。
- review の drag が重い window を残す場合は promotion しない。

## 変更履歴
| 日付 | 変更内容 | 変更者 |
| --- | --- | --- |
| 2026-03-19 | 初版作成 | Portfolio Integrator |
