---
id: PORTFOLIO-MULTIPAIR-01
title: Multi-pair Preparation from Shadow Gate
owners:
  - Portfolio Integrator
review_cycle_days: 30
linked_fr:
  - FR-55
  - FR-62
docops:
  related_commands:
    - tradectl portfolio next-stage --phase multi_pair_preparation
    - tradectl portfolio candidates
    - tradectl portfolio admit
---

# PORTFOLIO-MULTIPAIR-01: Shadow soak後のmulti-pair preparation実行

> **Runbook版数**: v0.2  
> **最終更新日**: 2026-03-21  
> **最終更新者**: Portfolio Integrator

## 目的
- shadow soak gate が `multi_pair_preparation` を返したときに、次の通貨ペア導入準備を packet 化して実行する。
- validation、candidate snapshot、admission snapshot を同じ packet にまとめる。

## トリガー
- `daily_shadow_review_summary.soak_summary.ready_for_transition=true`
- `qualified_next_phase=multi_pair_preparation`

## 事前準備
1. 既定の first pair は `EURUSD`。明示 override がなければこれを使う。
2. その通貨ペアの merged parquet を用意する。未指定時は curated merged を自動解決する。
3. `profile / data_dir / feature_config / data_manifest` が現行 baseline と互換であることを確認する。

## 実行
1. packet を生成する。  
   `tradectl portfolio next-stage --phase multi_pair_preparation --next-symbol EURUSD --data-path <merged_parquet>`
2. 実行する。  
   `tradectl portfolio next-stage --phase multi_pair_preparation --next-symbol EURUSD --data-path <merged_parquet> --run`
3. `USDJPY-only` baseline validation と `USDJPY + next_symbol` cross-pair validation を比較して、pair 追加の前提が崩れていないか確認する。
4. candidate snapshot、admit snapshot、pair-scoped exposure bucket / portfolio group が不自然でないか確認する。

## 証跡
- `reports/analysis/shadow/shadow_multi_pair_preparation_<stamp>.json`
- `reports/analysis/shadow/shadow_multi_pair_preparation_<stamp>.md`
- `reports/analysis/shadow/shadow_multi_pair_<pair>_baseline_validation.json`
- `reports/analysis/shadow/shadow_multi_pair_<pair>_validation.json`
- `reports/analysis/shadow/portfolio_candidates_snapshot.json`
- `reports/analysis/shadow/portfolio_admit_snapshot.json`

## 判定
- `USDJPY-only` 대비 cross-pair validation で PF 低下と DD 悪化が許容を超える pair は保留。
- candidate/admit snapshot で exposure bucket や slot conflict が不自然なら保留。
- 最初の有効化は baseline 直接昇格ではなく shadow-first。

## 変更履歴
| 日付 | 変更内容 | 変更者 |
| --- | --- | --- |
| 2026-03-21 | EURUSD first-pair default, cross-pair validation, pair-scoped contract を追記 | Portfolio Integrator |
| 2026-03-19 | 初版作成 | Portfolio Integrator |
